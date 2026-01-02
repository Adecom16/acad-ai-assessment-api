"""
Management command to set up demo data for the Mini Assessment Engine.
Creates demo users, courses, exams, and questions.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from assessments.models import Course, Exam, Question, UserProfile


class Command(BaseCommand):
    help = 'Set up demo data for testing'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('\n🎓 Setting up Mini Assessment Engine Demo Data...\n'))
        
        # Create student
        student, created = User.objects.get_or_create(
            username='student',
            defaults={
                'email': 'student@example.com',
                'first_name': 'Test',
                'last_name': 'Student',
                'is_active': True
            }
        )
        if created:
            student.set_password('student123')
            student.save()
            student.profile.role = UserProfile.Role.STUDENT
            student.profile.save()
            self.stdout.write(self.style.SUCCESS('✓ Created student: student / student123'))
        else:
            self.stdout.write('  Student user already exists')
        
        student_token, _ = Token.objects.get_or_create(user=student)

        # Create educator
        educator, created = User.objects.get_or_create(
            username='educator',
            defaults={
                'email': 'educator@example.com',
                'first_name': 'Test',
                'last_name': 'Educator',
                'is_staff': True,
                'is_active': True
            }
        )
        if created:
            educator.set_password('educator123')
            educator.save()
            educator.profile.role = UserProfile.Role.EDUCATOR
            educator.profile.institution = 'Acad AI University'
            educator.profile.save()
            self.stdout.write(self.style.SUCCESS('✓ Created educator: educator / educator123'))
        else:
            self.stdout.write('  Educator user already exists')
        
        educator_token, _ = Token.objects.get_or_create(user=educator)

        # Create admin
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
            admin.profile.role = UserProfile.Role.ADMIN
            admin.profile.save()
            self.stdout.write(self.style.SUCCESS('✓ Created admin: admin / admin123'))
        else:
            self.stdout.write('  Admin user already exists')

        admin_token, _ = Token.objects.get_or_create(user=admin)

        # Create course
        course, _ = Course.objects.get_or_create(
            code='CS101',
            defaults={
                'name': 'Introduction to Python',
                'description': 'Learn Python programming fundamentals'
            }
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Course: {course.name} ({course.code})'))

        # Create exam
        exam, created = Exam.objects.get_or_create(
            title='Python Basics Quiz',
            course=course,
            defaults={
                'description': 'Test your Python knowledge with this quiz',
                'duration_minutes': 30,
                'passing_score': 60,
                'max_attempts': 3,
                'status': Exam.Status.PUBLISHED,
                'browser_lockdown': True,
                'allow_copy_paste': False,
                'max_tab_switches': 3,
                'created_by': educator
            }
        )

        if created:
            # Create questions
            Question.objects.create(
                exam=exam,
                question_type='mcq',
                text='What is the output of print(type([]))?',
                points=2,
                order=1,
                choices=["<class 'list'>", "<class 'tuple'>", "<class 'dict'>", "<class 'set'>"],
                expected_answer='0'
            )
            Question.objects.create(
                exam=exam,
                question_type='tf',
                text='Python is a statically typed programming language.',
                points=1,
                order=2,
                choices=['True', 'False'],
                expected_answer='1'
            )
            Question.objects.create(
                exam=exam,
                question_type='short',
                text='What is a Python decorator? Explain briefly.',
                points=3,
                order=3,
                expected_answer='A decorator is a function that wraps another function to extend its behavior without modifying it directly.',
                grading_rubric='Must mention: function wrapper, extends/modifies behavior, without changing original'
            )
            Question.objects.create(
                exam=exam,
                question_type='essay',
                text='Compare and contrast Python lists and tuples. Include examples.',
                points=5,
                order=4,
                expected_answer='Lists are mutable sequences using square brackets [], while tuples are immutable sequences using parentheses (). Lists can be modified after creation, tuples cannot. Use lists for collections that may change, tuples for fixed data.',
                grading_rubric='Key points: mutability difference, syntax ([] vs ()), use cases, examples'
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Exam: {exam.title} with 4 questions'))
        else:
            self.stdout.write(f'  Exam already exists: {exam.title}')

        # Print summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('🎉 Demo Setup Complete!'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        self.stdout.write('\n📋 Demo Accounts:')
        self.stdout.write('  ┌─────────────┬─────────────┬──────────────┐')
        self.stdout.write('  │ Role        │ Username    │ Password     │')
        self.stdout.write('  ├─────────────┼─────────────┼──────────────┤')
        self.stdout.write('  │ Student     │ student     │ student123   │')
        self.stdout.write('  │ Educator    │ educator    │ educator123  │')
        self.stdout.write('  │ Admin       │ admin       │ admin123     │')
        self.stdout.write('  └─────────────┴─────────────┴──────────────┘')
        
        self.stdout.write('\n🔑 API Tokens:')
        self.stdout.write(f'  Student:  {student_token.key}')
        self.stdout.write(f'  Educator: {educator_token.key}')
        self.stdout.write(f'  Admin:    {admin_token.key}')
        
        self.stdout.write('\n📚 API Documentation:')
        self.stdout.write('  Swagger UI: http://localhost:8000/api/docs/')
        self.stdout.write('  ReDoc:      http://localhost:8000/api/redoc/')
        
        self.stdout.write('\n🧪 Test API:')
        self.stdout.write(f'  curl -H "Authorization: Token {student_token.key}" http://localhost:8000/api/exams/')
        self.stdout.write('')
