"""
Test cases for Mini Assessment Engine.
Covers grading, authentication, and submission security.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.authtoken.models import Token

from .models import Course, Exam, Question, Submission, OTPToken, UserProfile
from .grading import MockGradingService


class MockGradingServiceTests(TestCase):
    """Tests for the mock grading service."""
    
    def setUp(self):
        self.grader = MockGradingService()

    def test_mcq_correct(self):
        """Test MCQ grading with correct answer."""
        result = self.grader.grade_answer(
            question_type='mcq', student_answer='', expected_answer='0',
            max_points=2.0, choices=['A', 'B', 'C'], selected_choice=0
        )
        self.assertEqual(result.points_earned, 2.0)
        self.assertTrue(result.is_correct)

    def test_mcq_wrong(self):
        """Test MCQ grading with wrong answer."""
        result = self.grader.grade_answer(
            question_type='mcq', student_answer='', expected_answer='0',
            max_points=2.0, choices=['A', 'B', 'C'], selected_choice=1
        )
        self.assertEqual(result.points_earned, 0)
        self.assertFalse(result.is_correct)

    def test_true_false_correct(self):
        """Test True/False grading."""
        result = self.grader.grade_answer(
            question_type='tf', student_answer='', expected_answer='1',
            max_points=1.0, choices=['True', 'False'], selected_choice=1
        )
        self.assertEqual(result.points_earned, 1.0)
        self.assertTrue(result.is_correct)

    def test_short_answer_similarity(self):
        """Test short answer grading with text similarity."""
        result = self.grader.grade_answer(
            question_type='short',
            student_answer='A decorator wraps a function to extend behavior',
            expected_answer='A decorator is a function that wraps another function to extend its behavior',
            max_points=3.0
        )
        self.assertGreater(result.points_earned, 0)
        self.assertEqual(result.grading_method, 'tfidf_similarity')

    def test_empty_answer(self):
        """Test grading with empty answer."""
        result = self.grader.grade_answer(
            question_type='short', student_answer='',
            expected_answer='Expected', max_points=3.0
        )
        self.assertEqual(result.points_earned, 0)
        self.assertFalse(result.is_correct)

    def test_essay_with_rubric(self):
        """Test essay grading with rubric keywords."""
        result = self.grader.grade_answer(
            question_type='essay',
            student_answer='Lists are mutable collections that can be modified. Tuples are immutable.',
            expected_answer='Lists are mutable, tuples are immutable. Lists use [], tuples use ().',
            max_points=5.0,
            grading_rubric='Key points: mutability, syntax differences'
        )
        self.assertGreater(result.points_earned, 0)


class OTPTokenTests(TestCase):
    """Tests for OTP token functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'testpass123')

    def test_otp_generation(self):
        """Test OTP code generation."""
        otp, plain_code = OTPToken.create_otp(
            email='test@test.com',
            purpose=OTPToken.Purpose.EMAIL_VERIFICATION,
            user=self.user
        )
        self.assertEqual(len(plain_code), 6)
        self.assertTrue(plain_code.isdigit())
        self.assertFalse(otp.is_used)

    def test_otp_verification_success(self):
        """Test successful OTP verification."""
        otp, plain_code = OTPToken.create_otp(
            email='test@test.com',
            purpose=OTPToken.Purpose.EMAIL_VERIFICATION,
            user=self.user
        )
        
        success, message, verified_otp = OTPToken.verify_otp(
            email='test@test.com',
            code=plain_code,
            purpose=OTPToken.Purpose.EMAIL_VERIFICATION
        )
        
        self.assertTrue(success)
        self.assertEqual(verified_otp.id, otp.id)

    def test_otp_verification_wrong_code(self):
        """Test OTP verification with wrong code."""
        otp, plain_code = OTPToken.create_otp(
            email='test@test.com',
            purpose=OTPToken.Purpose.EMAIL_VERIFICATION,
            user=self.user
        )
        
        success, message, verified_otp = OTPToken.verify_otp(
            email='test@test.com',
            code='000000',
            purpose=OTPToken.Purpose.EMAIL_VERIFICATION
        )
        
        self.assertFalse(success)
        self.assertIn('Invalid OTP', message)

    def test_otp_invalidation_on_new_request(self):
        """Test that old OTPs are invalidated when new one is created."""
        otp1, code1 = OTPToken.create_otp(
            email='test@test.com',
            purpose=OTPToken.Purpose.EMAIL_VERIFICATION,
            user=self.user
        )
        
        otp2, code2 = OTPToken.create_otp(
            email='test@test.com',
            purpose=OTPToken.Purpose.EMAIL_VERIFICATION,
            user=self.user
        )
        
        otp1.refresh_from_db()
        self.assertTrue(otp1.is_used)
        self.assertFalse(otp2.is_used)


class AuthenticationTests(APITestCase):
    """Tests for authentication endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'testpass123')
        self.user.is_active = True
        self.user.save()
        self.token = Token.objects.create(user=self.user)

    def test_login_success(self):
        """Test successful login."""
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)

    def test_login_wrong_password(self):
        """Test login with wrong password."""
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'wrongpass'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_inactive_user(self):
        """Test login with inactive user."""
        self.user.is_active = False
        self.user.save()
        
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_protected_endpoint_without_auth(self):
        """Test accessing protected endpoint without authentication."""
        response = self.client.get('/api/exams/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_protected_endpoint_with_token(self):
        """Test accessing protected endpoint with valid token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get('/api/exams/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout(self):
        """Test logout invalidates token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.post('/api/auth/logout/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Token should be invalid now
        response = self.client.get('/api/exams/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_view(self):
        """Test profile endpoint."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get('/api/auth/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')


class SubmissionSecurityTests(APITestCase):
    """Tests for submission security and ownership."""
    
    def setUp(self):
        self.user1 = User.objects.create_user('user1', 'u1@test.com', 'pass123')
        self.user1.is_active = True
        self.user1.save()
        self.user2 = User.objects.create_user('user2', 'u2@test.com', 'pass123')
        self.user2.is_active = True
        self.user2.save()
        self.token1 = Token.objects.create(user=self.user1)
        self.token2 = Token.objects.create(user=self.user2)

        self.course = Course.objects.create(name='Test', code='TEST101')
        self.exam = Exam.objects.create(
            title='Test Exam', course=self.course,
            duration_minutes=30, status=Exam.Status.PUBLISHED
        )
        self.submission = Submission.objects.create(
            student=self.user1, exam=self.exam, status=Submission.Status.IN_PROGRESS
        )

    def test_user_sees_own_submission(self):
        """Test user can view their own submission."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token1.key}')
        response = self.client.get(f'/api/submissions/{self.submission.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_see_others_submission(self):
        """Test user cannot view another user's submission."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token2.key}')
        response = self.client.get(f'/api/submissions/{self.submission.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_shows_only_own_submissions(self):
        """Test submission list only shows user's own submissions."""
        Submission.objects.create(student=self.user2, exam=self.exam, status=Submission.Status.IN_PROGRESS)
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token1.key}')
        response = self.client.get('/api/submissions/')
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.submission.id)


class RoleBasedAccessTests(APITestCase):
    """Tests for role-based access control."""
    
    def setUp(self):
        # Create student
        self.student = User.objects.create_user('student', 'student@test.com', 'pass123')
        self.student.is_active = True
        self.student.save()
        self.student.profile.role = UserProfile.Role.STUDENT
        self.student.profile.save()
        self.student_token = Token.objects.create(user=self.student)
        
        # Create educator
        self.educator = User.objects.create_user('educator', 'educator@test.com', 'pass123')
        self.educator.is_active = True
        self.educator.is_staff = True
        self.educator.save()
        self.educator.profile.role = UserProfile.Role.EDUCATOR
        self.educator.profile.save()
        self.educator_token = Token.objects.create(user=self.educator)
        
        self.course = Course.objects.create(name='Test', code='TEST101')

    def test_student_cannot_create_course(self):
        """Test student cannot create courses."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.student_token.key}')
        response = self.client.post('/api/courses/', {
            'name': 'New Course',
            'code': 'NEW101'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_educator_can_create_course(self):
        """Test educator can create courses."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.educator_token.key}')
        response = self.client.post('/api/courses/', {
            'name': 'New Course',
            'code': 'NEW101'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_student_can_read_courses(self):
        """Test student can read courses."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.student_token.key}')
        response = self.client.get('/api/courses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
