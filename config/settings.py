"""
Django settings for Mini Assessment Engine.
Production-ready configuration with security best practices.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Security Settings
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,.onrender.com').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'drf_spectacular',
    'drf_spectacular_sidecar',
    # Local apps
    'assessments',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Custom security middleware
    'assessments.middleware.SecurityHeadersMiddleware',
    'assessments.middleware.RequestValidationMiddleware',
    'assessments.middleware.ExamSessionSecurityMiddleware',
    'assessments.middleware.IPConsistencyMiddleware',
    'assessments.middleware.ConcurrentSessionMiddleware',
    'assessments.middleware.ExamTimingMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database - PostgreSQL
# Use DATABASE_URL if available (Render), otherwise use individual env vars
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'assessment_db'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise for static files in production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'submission': '10/minute',
        'auth': '5/minute',
        'otp': '3/minute',
        'burst': '60/minute',
    },
}

# DRF Spectacular (OpenAPI/Swagger) Settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'Mini Assessment Engine API',
    'DESCRIPTION': '''
A Django REST API for academic assessments built for **Acad AI**.

## Authentication
Use Token authentication: `Authorization: Token your-token-here`

## Demo Accounts
| Role | Username | Password |
|------|----------|----------|
| Student | student | student123 |
| Educator | educator | educator123 |
| Admin | admin | admin123 |

## User Roles
- **Student**: Take exams, view submissions, get certificates
- **Educator**: Create/manage exams, enroll students, view analytics
- **Admin**: Full platform access
''',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': False,
        'filter': True,
        'docExpansion': 'list',
        'defaultModelsExpandDepth': 2,
        'defaultModelExpandDepth': 2,
    },
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',
    'TAGS': [
        {'name': 'Authentication', 'description': 'User registration, login, OTP verification, and password reset.'},
        {'name': 'Dashboards', 'description': 'Admin and educator analytics dashboards.'},
        {'name': 'Courses', 'description': 'Course management (CRUD operations).'},
        {'name': 'Exams', 'description': 'Exam creation, publishing, and management.'},
        {'name': 'Questions', 'description': 'Question management (MCQ, True/False, Short Answer, Essay).'},
        {'name': 'Submissions', 'description': 'Student exam submissions and automated grading.'},
        {'name': 'Enrollment', 'description': 'Student enrollment and invite link management.'},
        {'name': 'Analytics', 'description': 'Exam analytics and plagiarism detection.'},
        {'name': 'Export', 'description': 'CSV export for results and reports.'},
        {'name': 'Bulk Import', 'description': 'Bulk question import from CSV/JSON.'},
        {'name': 'Grade Review', 'description': 'Manual grade adjustments by educators.'},
        {'name': 'Certificates', 'description': 'Completion certificates for passed exams.'},
        {'name': 'Leaderboard', 'description': 'Student rankings and performance tracking.'},
    ],
    'ENUM_NAME_OVERRIDES': {
        'ExamStatusEnum': 'assessments.models.exam.Exam.Status',
        'SubmissionStatusEnum': 'assessments.models.submission.Submission.Status',
        'UserRoleEnum': 'assessments.models.user_profile.UserProfile.Role',
        'OTPPurposeEnum': 'assessments.models.otp.OTPToken.Purpose',
    },
    # Security - only show TokenAuth
    'SECURITY': [{'TokenAuth': []}],
    'COMPONENT_SPLIT_REQUEST': True,
    'PREPROCESSING_HOOKS': [],
    'POSTPROCESSING_HOOKS': ['config.spectacular_hooks.remove_extra_security_schemes'],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'TokenAuth': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'Authorization',
                'description': 'Token-based authentication. Format: `Token <your-token>`'
            }
        }
    },
}

# Grading Service Configuration
GRADING_SERVICE = {
    'DEFAULT_BACKEND': os.getenv('GRADING_BACKEND', 'mock'),  # 'mock' or 'llm'
    'LLM_API_KEY': os.getenv('LLM_API_KEY', ''),
    'LLM_MODEL': os.getenv('LLM_MODEL', 'gpt-3.5-turbo'),
    'GRADING_TIMEOUT': 30,  # seconds
}

# OTP Configuration
OTP_SETTINGS = {
    'EXPIRY_MINUTES': 10,
    'MAX_ATTEMPTS': 5,
    'CODE_LENGTH': 6,
}

# Email Configuration
# Supports: Gmail SMTP, Mailtrap, or any SMTP provider
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'sandbox.smtp.mailtrap.io')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 2525))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Assessment Engine <noreply@acadai.com>')

# Frontend URL for email links
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:8000')

# Security Settings (Production)
if not DEBUG:
    # HTTPS settings
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # Cookie security
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    
    # HSTS
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Content security
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'

# Session security
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 3600  # 1 hour

# Password hashing (use Argon2 for better security)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

# Logging configuration for security events
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'assessments': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Create logs directory
import os
os.makedirs(BASE_DIR / 'logs', exist_ok=True)
