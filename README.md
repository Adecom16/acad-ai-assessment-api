# Mini Assessment Engine API

Django REST API for academic assessments - Acad AI Backend.

## Tech Stack

- Django 5.0 + Django REST Framework
- PostgreSQL
- Token Authentication with OTP verification
- TF-IDF grading (scikit-learn)
- Swagger/OpenAPI documentation

## Features

- Three roles: Student, Educator, Admin
- Question types: MCQ, True/False, Short Answer, Essay
- Automated grading with anti-cheating detection
- Email notifications (Mailtrap/SMTP)
- Exam enrollment with invite links
- Plagiarism detection
- Analytics and leaderboards
- Bulk import (CSV/JSON)
- Completion certificates

## Quick Start

```bash
# Setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Configure
copy .env.example .env
# Edit .env with your database and email settings

# Database
python manage.py migrate
python manage.py setup_demo

# Run
python manage.py runserver
```

API Docs: http://localhost:8000/api/docs/

## Demo Accounts

| Role | Username | Password |
|------|----------|----------|
| Student | student | student123 |
| Educator | educator | educator123 |
| Admin | admin | admin123 |

## Authentication

```
Authorization: Token your-token-here
```

## Main Endpoints

### Auth
- `POST /api/auth/register/` - Register (sends OTP)
- `POST /api/auth/verify-otp/` - Verify email
- `POST /api/auth/login/` - Get token
- `POST /api/auth/logout/` - Logout
- `POST /api/auth/forgot-password/` - Password reset

### Courses
- `GET/POST /api/courses/` - List/Create courses
- `GET/PUT/DELETE /api/courses/{id}/` - Course detail

### Exams
- `GET/POST /api/exams/` - List/Create exams
- `POST /api/exams/{id}/publish/` - Publish exam
- `GET /api/exams/{id}/analytics/` - Exam analytics
- `GET /api/exams/{id}/export/` - Export results CSV

### Questions
- `GET/POST /api/questions/` - List/Create questions
- `POST /api/questions/bulk-import/` - Bulk import (CSV/JSON file)
- `GET /api/questions/search/` - Search questions

### Submissions
- `POST /api/submissions/` - Start exam
- `POST /api/submissions/{id}/submit/` - Submit answers
- `POST /api/submissions/{id}/report_activity/` - Report cheating activity

### Enrollment
- `POST /api/enrollments/` - Enroll student
- `POST /api/enrollments/join/` - Join via invite code
- `POST /api/exams/{id}/generate_invite/` - Generate invite link

### Grade Review
- `GET /api/answers/query/` - Query answers by student/exam
- `PATCH /api/answers/{id}/review/` - Manual grade adjustment

### Certificates
- `GET /api/certificates/` - List certificates
- `GET /api/certificates/verify/{code}/` - Verify certificate

### Dashboards
- `GET /api/dashboard/admin/` - Admin stats
- `GET /api/dashboard/educator/` - Educator stats
- `GET /api/leaderboard/` - Student rankings

## Security Features

- SQL injection and XSS detection
- Rate limiting
- IP consistency monitoring
- Concurrent session prevention
- Exam timing enforcement
- Suspicion scoring for flagged submissions

### Anti-Cheating Tracking
- Tab switches
- Copy/paste attempts
- Focus lost events
- Right-click attempts
- Keyboard shortcuts (Ctrl+C/V)
- IP changes during exam

## Grading

| Type | Method |
|------|--------|
| MCQ/TF | Exact match |
| Short Answer | TF-IDF + keyword matching |
| Essay | Multi-factor analysis with rubric |

Anti-cheating: Gibberish detection, minimum length, required keywords.

## Environment Variables

```env
# Django
DJANGO_SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (Option 1: URL)
DATABASE_URL=postgres://user:pass@host:5432/dbname

# Database (Option 2: Individual)
DB_NAME=assessment_db
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432

# Email (Mailtrap recommended for testing)
EMAIL_HOST=sandbox.smtp.mailtrap.io
EMAIL_PORT=2525
EMAIL_HOST_USER=your-username
EMAIL_HOST_PASSWORD=your-password

# Grading
GRADING_BACKEND=mock
```

## Deployment (Render)

1. Push to GitHub
2. Connect repo to Render
3. Render auto-detects `render.yaml`
4. Set environment variables in Render dashboard
5. Deploy

## Project Structure

```
├── config/
│   ├── settings.py
│   └── urls.py
├── assessments/
│   ├── api/
│   │   ├── views.py
│   │   ├── serializers.py
│   │   └── auth_views.py
│   ├── grading/
│   │   └── mock_grader.py
│   ├── models/
│   ├── services/
│   │   ├── analytics.py
│   │   ├── notification.py
│   │   ├── plagiarism.py
│   │   ├── certificate.py
│   │   └── bulk_import.py
│   └── middleware.py
├── render.yaml
├── build.sh
└── requirements.txt
```

---

Acad AI Backend Assessment
