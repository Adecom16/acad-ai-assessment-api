# Technical Documentation - Mini Assessment Engine

## Overview

This is a Django REST API for academic assessments built for the **Acad AI Backend Assessment**. It demonstrates production-ready backend development with secure authentication, automated grading, and comprehensive API documentation.

---

## Tech Stack

| Technology | Purpose |
|------------|---------|
| **Django 5.x** | Web framework |
| **Django REST Framework** | API development |
| **PostgreSQL** | Database |
| **drf-spectacular** | OpenAPI/Swagger documentation |
| **scikit-learn** | TF-IDF grading algorithm |
| **Argon2** | Password hashing |

---

## Project Structure

```
├── config/                     # Django configuration
│   ├── settings.py            # Main settings (DB, auth, throttling)
│   └── urls.py                # Root URL routing
│
├── assessments/
│   ├── models/                # Database models
│   │   ├── course.py          # Course model
│   │   ├── exam.py            # Exam model with anti-cheat settings
│   │   ├── question.py        # Question types (MCQ, TF, Short, Essay)
│   │   ├── submission.py      # Student submissions
│   │   ├── answer.py          # Individual answers
│   │   ├── user_profile.py    # Role-based profiles
│   │   ├── otp.py             # OTP tokens for verification
│   │   ├── enrollment.py      # Exam enrollments & invite links
│   │   └── audit_log.py       # Security event logging
│   │
│   ├── api/
│   │   ├── views.py           # Main API endpoints
│   │   ├── auth_views.py      # Authentication endpoints
│   │   ├── serializers.py     # Request/response schemas
│   │   └── auth_serializers.py # Auth-specific serializers
│   │
│   ├── grading/               # Grading system
│   │   ├── base.py            # Abstract grader interface
│   │   ├── mock_grader.py     # TF-IDF based grading
│   │   ├── llm_grader.py      # OpenAI integration
│   │   └── factory.py         # Grader selection
│   │
│   ├── services/              # Business logic
│   │   ├── plagiarism.py      # Plagiarism detection
│   │   ├── analytics.py       # Exam analytics
│   │   ├── leaderboard.py     # Rankings & leaderboards
│   │   ├── certificate.py     # Certificate generation
│   │   ├── notification.py    # Email notifications
│   │   └── bulk_import.py     # CSV/JSON import
│   │
│   ├── permissions.py         # Custom permission classes
│   ├── throttling.py          # Rate limiting
│   └── middleware.py          # Security middleware
```

---

## Database Design

### Entity Relationship

```
User (Django built-in)
  │
  ├── UserProfile (1:1) ──── role, institution, department
  │
  ├── Submission (1:N) ──── exam attempts
  │     └── Answer (1:N) ── individual question responses
  │
  └── OTPToken (1:N) ────── verification codes

Course (1:N) ──── Exam (1:N) ──── Question
                    │
                    └── ExamEnrollment (M:N with User)
                    └── ExamInviteLink (shareable links)
```

### Key Models

**Exam Model** - Core assessment entity
```python
class Exam(models.Model):
    title = models.CharField(max_length=200)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    duration_minutes = models.PositiveIntegerField(default=60)
    passing_score = models.DecimalField(default=60)
    max_attempts = models.PositiveIntegerField(default=1)
    status = models.CharField(choices=Status.choices)  # draft/published/archived
    
    # Anti-cheating
    shuffle_questions = models.BooleanField(default=False)
    browser_lockdown = models.BooleanField(default=False)
    max_tab_switches = models.PositiveIntegerField(default=3)
```

**Question Model** - Supports multiple types
```python
class Question(models.Model):
    TYPES = [('mcq', 'Multiple Choice'), ('tf', 'True/False'), 
             ('short', 'Short Answer'), ('essay', 'Essay')]
    
    exam = models.ForeignKey(Exam, related_name='questions')
    question_type = models.CharField(choices=TYPES)
    text = models.TextField()
    points = models.DecimalField()
    choices = models.JSONField(null=True)  # For MCQ
    expected_answer = models.TextField()
    grading_rubric = models.TextField(blank=True)  # For essay grading
```

**Submission Model** - Tracks exam attempts
```python
class Submission(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    status = models.CharField(choices=Status.choices)  # in_progress/submitted/grading/graded/flagged
    score = models.DecimalField(null=True)
    percentage = models.DecimalField(null=True)
    passed = models.BooleanField(null=True)
    
    # Anti-cheating tracking
    tab_switch_count = models.PositiveIntegerField(default=0)
    copy_paste_attempts = models.PositiveIntegerField(default=0)
    suspicious_activity_flags = models.JSONField(default=list)
    
    # Indexing for performance
    class Meta:
        indexes = [
            models.Index(fields=['student', 'exam']),
            models.Index(fields=['status']),
            models.Index(fields=['-submitted_at']),
        ]
```

---

## Authentication System

### OTP-Based Registration Flow

```
1. POST /api/auth/register/
   └── Creates inactive user
   └── Generates 6-digit OTP (SHA256 hashed)
   └── Sends OTP via email

2. POST /api/auth/verify-otp/
   └── Verifies OTP code
   └── Activates user account
   └── Returns auth token

3. POST /api/auth/login/
   └── Validates credentials
   └── Returns auth token
```

### OTP Security Implementation

```python
class OTPToken(models.Model):
    email = models.EmailField()
    code_hash = models.CharField(max_length=64)  # SHA256 hash
    purpose = models.CharField(choices=Purpose.choices)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = 5
    
    @classmethod
    def create_otp(cls, email, purpose, user=None):
        # Invalidate previous OTPs
        cls.objects.filter(email=email, purpose=purpose, is_used=False).update(is_used=True)
        
        # Generate 6-digit code
        plain_code = ''.join(random.choices('0123456789', k=6))
        code_hash = hashlib.sha256(plain_code.encode()).hexdigest()
        
        otp = cls.objects.create(
            email=email,
            code_hash=code_hash,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        return otp, plain_code  # plain_code sent via email
    
    @classmethod
    def verify_otp(cls, email, code, purpose):
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        otp = cls.objects.filter(
            email=email, 
            code_hash=code_hash,
            purpose=purpose,
            is_used=False
        ).first()
        
        if not otp:
            return False, "Invalid OTP"
        if otp.is_expired:
            return False, "OTP expired"
        if otp.attempts >= otp.max_attempts:
            return False, "Max attempts exceeded"
        
        otp.is_used = True
        otp.save()
        return True, "Verified", otp
```

### Role-Based Access Control

```python
class UserProfile(models.Model):
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        EDUCATOR = 'educator', 'Educator'
        ADMIN = 'admin', 'Admin'
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
```

**Permission Classes:**
```python
class IsEducatorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        profile = getattr(request.user, 'profile', None)
        return profile and profile.role in ['educator', 'admin']

class IsOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.student == request.user
```

---

## Grading System

### Architecture (Strategy Pattern)

```python
# Base interface
class BaseGradingService(ABC):
    @abstractmethod
    def grade_answer(self, question_type, student_answer, expected_answer, 
                     max_points, choices=None, selected_choice=None, 
                     grading_rubric=None) -> GradingResult:
        pass

# Factory for selecting grader
def get_grading_service() -> BaseGradingService:
    backend = settings.GRADING_SERVICE.get('DEFAULT_BACKEND', 'mock')
    if backend == 'llm':
        return LLMGradingService()
    return MockGradingService()
```

### Mock Grading (TF-IDF + Keyword Matching)

```python
class MockGradingService(BaseGradingService):
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            ngram_range=(1, 2),
            max_features=1000
        )
    
    def grade_answer(self, question_type, student_answer, expected_answer, max_points, **kwargs):
        if question_type == 'mcq':
            return self._grade_mcq(kwargs.get('selected_choice'), expected_answer, max_points)
        elif question_type == 'tf':
            return self._grade_true_false(student_answer, expected_answer, max_points)
        elif question_type == 'short':
            return self._grade_short_answer(student_answer, expected_answer, max_points)
        elif question_type == 'essay':
            return self._grade_essay(student_answer, expected_answer, max_points, 
                                     kwargs.get('grading_rubric'))
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """TF-IDF cosine similarity"""
        try:
            tfidf_matrix = self.vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similarity)
        except:
            return 0.0
    
    def _calculate_keyword_density(self, student_answer: str, expected_answer: str) -> float:
        """Keyword matching score"""
        expected_words = set(expected_answer.lower().split())
        student_words = set(student_answer.lower().split())
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', ...}
        expected_keywords = expected_words - stop_words
        student_keywords = student_words - stop_words
        
        if not expected_keywords:
            return 1.0
        
        matches = len(expected_keywords & student_keywords)
        return matches / len(expected_keywords)
    
    def _grade_short_answer(self, student_answer, expected_answer, max_points):
        similarity = self._calculate_similarity(student_answer, expected_answer)
        keyword_score = self._calculate_keyword_density(student_answer, expected_answer)
        
        # Weighted combination: 60% similarity, 40% keywords
        final_score = (similarity * 0.6) + (keyword_score * 0.4)
        points = max_points * final_score
        
        return GradingResult(
            points_earned=round(points, 2),
            max_points=max_points,
            is_correct=final_score >= 0.7,
            confidence=final_score,
            feedback=self._generate_feedback(final_score),
            grading_method='tfidf_keyword'
        )
```

### LLM Integration (OpenAI)

```python
class LLMGradingService(BaseGradingService):
    def __init__(self):
        self.api_key = settings.GRADING_SERVICE.get('LLM_API_KEY')
        self.model = settings.GRADING_SERVICE.get('LLM_MODEL', 'gpt-3.5-turbo')
        self.fallback = MockGradingService()  # Fallback if LLM fails
    
    def _call_llm(self, prompt: str) -> dict:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={'Authorization': f'Bearer {self.api_key}'},
            json={
                'model': self.model,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3
            },
            timeout=30
        )
        return response.json()
    
    def grade_answer(self, question_type, student_answer, expected_answer, max_points, **kwargs):
        try:
            prompt = f"""Grade this answer:
Question Type: {question_type}
Expected Answer: {expected_answer}
Student Answer: {student_answer}
Max Points: {max_points}

Return JSON: {{"points": X, "feedback": "...", "confidence": 0.0-1.0}}"""
            
            result = self._call_llm(prompt)
            # Parse and return result
        except Exception as e:
            # Fallback to mock grading
            return self.fallback.grade_answer(...)
```

---

## Plagiarism Detection

```python
class PlagiarismDetector:
    def __init__(self, similarity_threshold=0.85):
        self.threshold = similarity_threshold
        self.vectorizer = TfidfVectorizer(stop_words='english')
    
    def check_exam_submissions(self, submissions):
        """Compare all submissions pairwise"""
        results = {'flagged_pairs': [], 'total_checked': 0}
        
        # Group answers by question
        answers_by_question = defaultdict(list)
        for submission in submissions:
            for answer in submission.answers.all():
                if answer.answer_text:
                    answers_by_question[answer.question_id].append({
                        'submission_id': submission.id,
                        'student': submission.student.username,
                        'text': answer.answer_text
                    })
        
        # Check each question's answers
        for question_id, answers in answers_by_question.items():
            if len(answers) < 2:
                continue
            
            texts = [a['text'] for a in answers]
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            similarity_matrix = cosine_similarity(tfidf_matrix)
            
            # Find pairs above threshold
            for i in range(len(answers)):
                for j in range(i + 1, len(answers)):
                    similarity = similarity_matrix[i][j]
                    if similarity >= self.threshold:
                        results['flagged_pairs'].append({
                            'student_1': answers[i]['student'],
                            'student_2': answers[j]['student'],
                            'similarity': round(similarity * 100, 2),
                            'question_id': question_id
                        })
        
        return results
```

---

## Query Optimization

### Using select_related and prefetch_related

```python
# Bad - N+1 queries
submissions = Submission.objects.all()
for s in submissions:
    print(s.student.username)  # Extra query each iteration
    print(s.exam.title)        # Extra query each iteration

# Good - 1 query with JOINs
submissions = Submission.objects.select_related('student', 'exam', 'exam__course')

# For reverse relations (many side)
submissions = Submission.objects.prefetch_related(
    Prefetch('answers', queryset=Answer.objects.select_related('question'))
)
```

### Annotations for Aggregations

```python
# Get exams with question count and total points
exams = Exam.objects.annotate(
    question_count=Count('questions'),
    total_points=Sum('questions__points')
)

# Leaderboard with window functions
from django.db.models.functions import DenseRank, PercentRank
from django.db.models import Window, F

submissions = Submission.objects.filter(
    exam_id=exam_id,
    status='graded'
).annotate(
    rank=Window(
        expression=DenseRank(),
        order_by=F('percentage').desc()
    ),
    percentile=Window(
        expression=PercentRank(),
        order_by=F('percentage').asc()
    )
).order_by('rank')
```

### Database Indexes

```python
class Submission(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['student', 'exam']),      # Frequent filter
            models.Index(fields=['status']),               # Status filtering
            models.Index(fields=['-submitted_at']),        # Ordering
            models.Index(fields=['exam', 'status']),       # Combined filter
        ]
```

---

## Rate Limiting

```python
# Custom throttle classes
class AuthRateThrottle(UserRateThrottle):
    rate = '5/minute'
    scope = 'auth'

class OTPRateThrottle(UserRateThrottle):
    rate = '3/minute'
    scope = 'otp'

class SubmissionRateThrottle(UserRateThrottle):
    rate = '10/minute'
    scope = 'submission'

# Applied in views
class LoginView(APIView):
    throttle_classes = [AuthRateThrottle]

class VerifyOTPView(APIView):
    throttle_classes = [OTPRateThrottle]
```

---

## Security Features

### Password Hashing (Argon2)

```python
# settings.py
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',  # Primary
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',  # Fallback
]
```

### Security Middleware

```python
class SecurityHeadersMiddleware:
    def __call__(self, request):
        response = self.get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response
```

### Audit Logging

```python
class AuditLog(models.Model):
    class EventType(models.TextChoices):
        LOGIN = 'login'
        LOGIN_FAILED = 'login_failed'
        EXAM_START = 'exam_start'
        EXAM_SUBMIT = 'exam_submit'
        SUSPICIOUS_ACTIVITY = 'suspicious_activity'
    
    event_type = models.CharField(choices=EventType.choices)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    description = models.TextField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    @classmethod
    def log(cls, event_type, description, request, user=None, metadata=None):
        cls.objects.create(
            event_type=event_type,
            user=user or getattr(request, 'user', None),
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            description=description,
            metadata=metadata or {}
        )
```

---

## API Documentation (drf-spectacular)

```python
# Decorating views
@extend_schema(
    tags=['Submissions'],
    summary="Submit exam answers",
    description="Submit answers and trigger automated grading.",
    request=SubmissionSubmitSerializer,
    responses={200: SubmissionDetailSerializer},
    examples=[
        OpenApiExample(
            'Request Example',
            value={"answers": [{"question_id": 1, "selected_choice": 0}]},
            request_only=True
        )
    ]
)
@action(detail=True, methods=['post'])
def submit(self, request, pk=None):
    ...
```

---

## Key Interview Talking Points

### 1. Why Django REST Framework?
- Built-in serialization, validation, authentication
- ViewSets reduce boilerplate code
- Excellent documentation support with drf-spectacular

### 2. Why TF-IDF for Grading?
- No external API dependencies (works offline)
- Fast and deterministic
- Handles semantic similarity better than exact matching
- Combined with keyword density for better accuracy

### 3. Why OTP over Email Verification Links?
- More secure (6-digit code vs long URL token)
- Better UX (user stays in app)
- Harder to intercept/share
- Time-limited (10 minutes)

### 4. How is Plagiarism Detection Implemented?
- TF-IDF vectorization of all answers
- Pairwise cosine similarity comparison
- Configurable threshold (default 85%)
- Flags suspicious pairs for manual review

### 5. Query Optimization Techniques Used
- `select_related` for foreign keys (reduces N+1)
- `prefetch_related` for reverse relations
- Database indexes on frequently filtered fields
- Window functions for efficient ranking

### 6. Security Measures
- Argon2 password hashing (OWASP recommended)
- SHA256 hashed OTP storage
- Rate limiting on auth endpoints
- Audit logging for security events
- Anti-cheating: tab switches, copy-paste detection

---

## Running the Project

```bash
# Setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Configure
copy .env.example .env
# Edit .env with your database credentials

# Database
python manage.py migrate
python manage.py setup_demo

# Run
python manage.py runserver

# Access
# API: http://localhost:8000/api/
# Swagger: http://localhost:8000/api/docs/
# Admin: http://localhost:8000/admin/
```

---

## Demo Accounts

| Role | Username | Password |
|------|----------|----------|
| Student | student | student123 |
| Educator | educator | educator123 |
| Admin | admin | admin123 |
