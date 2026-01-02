# Mini Assessment Engine

A production-ready Django REST API for academic assessments built for **Acad AI Backend Assessment**.

## Features

### Core Features
- Role-Based Access Control: Student, Educator, and Admin roles
- Secure Authentication: Token-based auth with OTP email verification
- Multiple Question Types: MCQ, True/False, Short Answer, Essay
- Automated Grading: TF-IDF similarity with anti-cheating detection
- Comprehensive Anti-Cheating System

### Advanced Features
- Email Notifications for all major activities
- Exam Enrollment System with shareable invite links
- Plagiarism Detection using TF-IDF text similarity
- Exam Analytics with difficulty and discrimination indices
- Leaderboard System with percentile rankings
- Bulk Import/Export via CSV/JSON file upload
- Completion Certificates with verification
- Manual Grade Review and adjustment

---

## Quick Start

```bash
# Clone and setup
git clone <repository>
cd mini-assessment-engine

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env         # Windows
cp .env.example .env           # Linux/Mac

# Database setup
python manage.py migrate
python manage.py setup_demo

# Run server
python manage.py runserver
```

## API Documentation

- Swagger UI: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/

---

## Authentication

### Demo Accounts
| Role | Username | Password |
|------|----------|----------|
| Student | student | student123 |
| Educator | educator | educator123 |
| Admin | admin | admin123 |

### Token Usage
```
Authorization: Token your-auth-token-here
```

---

## Security Features

### Multi-Layer Protection

**Request Security:**
- SQL injection detection and blocking
- XSS attack prevention
- Request validation middleware
- Rate limiting on all endpoints

**Exam Session Security:**
- IP consistency monitoring (detects VPN switching)
- Concurrent session prevention (one exam at a time)
- Exam timing enforcement (blocks late submissions)
- Browser fingerprint tracking

**Anti-Cheating Detection:**
| Activity | Detection Method |
|----------|-----------------|
| Tab switching | JavaScript event tracking |
| Copy/paste | Clipboard event monitoring |
| Focus lost | Window blur detection |
| Right-click | Context menu blocking |
| Keyboard shortcuts | Ctrl+C, Ctrl+V detection |
| IP changes | Mid-exam IP monitoring |
| Fast completion | Time analysis |
| Gibberish answers | Text validation |

**Suspicion Score (0-100):**
- Automatic scoring based on multiple factors
- Helps educators prioritize flagged submissions
- Weighted calculation considering all violations

### Security Headers
```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Permissions-Policy: geolocation=(), microphone=(), camera=()
Cache-Control: no-store (for API responses)
Content-Security-Policy: default-src 'self'
```

---

## Grading System

### Accurate Mock Grading

| Question Type | Method | Accuracy |
|--------------|--------|----------|
| MCQ | Exact match | 100% |
| True/False | Exact match | 100% |
| Short Answer | TF-IDF + keywords | High |
| Essay | Multi-factor analysis | High |

### Anti-Cheating in Grading
- Gibberish detection (keyboard mashing, random text)
- Minimum length requirements
- Dictionary word validation
- Required keyword enforcement

### Rubric Support
```json
{
  "grading_rubric": "Must mention: function, wrapper. Required: extends behavior"
}
```

---

## Email Notifications

### Student Notifications
- Registration OTP
- Exam invitation
- Enrollment confirmed
- Exam started
- Grades ready
- Grade updated
- Certificate available

### Educator Notifications
- New submission
- Flagged submission alert
- New enrollment

### Admin Notifications
- New user registration

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Register with OTP |
| POST | `/api/auth/verify-otp/` | Verify email |
| POST | `/api/auth/login/` | Get token |
| POST | `/api/auth/logout/` | Invalidate token |

### Exams
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/exams/` | List exams |
| POST | `/api/exams/` | Create exam |
| POST | `/api/exams/{id}/publish/` | Publish |
| GET | `/api/exams/{id}/analytics/` | Analytics |

### Submissions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/submissions/` | Start exam |
| POST | `/api/submissions/{id}/submit/` | Submit answers |
| POST | `/api/submissions/{id}/report_activity/` | Report cheating activity |

### Grade Review
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/answers/query/` | Query answers |
| PATCH | `/api/answers/{id}/review/` | Adjust grade |

---

## Request Examples

### Create Exam
```json
POST /api/exams/
{
  "title": "Python Quiz",
  "course_code": "CS101",
  "duration_minutes": 60,
  "passing_score": 70,
  "max_attempts": 3,
  "max_tab_switches": 3,
  "allow_copy_paste": false,
  "browser_lockdown": true
}
```

### Report Suspicious Activity
```json
POST /api/submissions/{id}/report_activity/
{
  "tab_switches": 2,
  "focus_lost": 1,
  "copy_paste_attempts": 0,
  "right_click_attempts": 1,
  "keyboard_shortcut_attempts": 0,
  "flags": ["window_resize_detected"]
}
```

---

## Role Permissions

| Action | Student | Educator | Admin |
|--------|:-------:|:--------:|:-----:|
| Take exams | Yes | Yes | Yes |
| View own submissions | Yes | Yes | Yes |
| Create exams | | Yes | Yes |
| Review grades | | Yes | Yes |
| View analytics | | Yes | Yes |
| Admin dashboard | | | Yes |

---

## Project Structure

```
├── config/
│   └── settings.py
├── assessments/
│   ├── api/
│   │   ├── views.py
│   │   └── serializers.py
│   ├── grading/
│   │   └── mock_grader.py
│   ├── models/
│   ├── services/
│   │   ├── notification.py
│   │   ├── plagiarism.py
│   │   └── analytics.py
│   └── middleware.py      # Security middleware
├── manage.py
└── requirements.txt
```

---

Built for **Acad AI Backend Assessment**
