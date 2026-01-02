from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.views import (
    # Dashboards
    AdminDashboardView, EducatorDashboardView,
    # Core Resources
    CourseViewSet, ExamViewSet, QuestionViewSet, SubmissionViewSet,
    # Enrollment
    ExamEnrollmentView, ExamEnrollmentDetailView,
    ExamInviteLinkView, ExamInviteLinkDetailView,
    JoinExamView, MyEnrollmentsView,
    # Certificates
    CertificateView, CertificateVerifyView,
    # Bulk Import
    BulkImportQuestionsView, BulkImportTemplateView,
    # Grade Review
    AnswerReviewView, AnswerQueryView,
    # Leaderboard & Progress
    ExamLeaderboardView, StudentRankingView, CourseLeaderboardView,
    TrendingPerformersView, StudentProgressView,
)
from .api.auth_views import (
    RegisterView, VerifyOTPView, ResendOTPView,
    LoginView, LogoutView,
    PasswordResetRequestView, PasswordResetConfirmView,
    ProfileView, ProfileUpdateView, ChangePasswordView,
)

# Router for ViewSets
router = DefaultRouter()
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'exams', ExamViewSet, basename='exam')
router.register(r'questions', QuestionViewSet, basename='question')
router.register(r'submissions', SubmissionViewSet, basename='submission')

urlpatterns = [
    # ============================================
    # AUTHENTICATION
    # ============================================
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('auth/resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/password-reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    path('auth/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('auth/profile/', ProfileView.as_view(), name='profile'),
    path('auth/profile/update/', ProfileUpdateView.as_view(), name='profile-update'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    
    # ============================================
    # DASHBOARDS
    # ============================================
    path('dashboard/admin/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('dashboard/educator/', EducatorDashboardView.as_view(), name='educator-dashboard'),
    
    # ============================================
    # LEADERBOARD & PROGRESS
    # ============================================
    path('leaderboard/exam/<int:exam_id>/', ExamLeaderboardView.as_view(), name='exam-leaderboard'),
    path('leaderboard/exam/<int:exam_id>/my-rank/', StudentRankingView.as_view(), name='my-ranking'),
    path('leaderboard/course/<int:course_id>/', CourseLeaderboardView.as_view(), name='course-leaderboard'),
    path('leaderboard/trending/', TrendingPerformersView.as_view(), name='trending-performers'),
    path('my-progress/', StudentProgressView.as_view(), name='my-progress'),
    
    # ============================================
    # ENROLLMENT
    # ============================================
    path('exams/<int:exam_id>/enrollments/', ExamEnrollmentView.as_view(), name='exam-enrollments'),
    path('exams/<int:exam_id>/invite-links/', ExamInviteLinkView.as_view(), name='exam-invite-links'),
    path('enrollments/<int:enrollment_id>/', ExamEnrollmentDetailView.as_view(), name='enrollment-detail'),
    path('invite-links/<int:link_id>/', ExamInviteLinkDetailView.as_view(), name='invite-link-detail'),
    path('join/', JoinExamView.as_view(), name='join-exam'),
    path('my-enrollments/', MyEnrollmentsView.as_view(), name='my-enrollments'),
    
    # ============================================
    # BULK IMPORT
    # ============================================
    path('exams/<int:exam_id>/import-questions/', BulkImportQuestionsView.as_view(), name='bulk-import'),
    path('import-template/', BulkImportTemplateView.as_view(), name='import-template'),
    
    # ============================================
    # GRADE REVIEW
    # ============================================
    path('answers/query/', AnswerQueryView.as_view(), name='answer-query'),
    path('answers/<int:answer_id>/review/', AnswerReviewView.as_view(), name='answer-review'),
    
    # ============================================
    # CERTIFICATES
    # ============================================
    path('certificates/<int:submission_id>/', CertificateView.as_view(), name='certificate'),
    path('certificates/verify/<str:cert_id>/', CertificateVerifyView.as_view(), name='certificate-verify'),
    
    # ============================================
    # CORE API ROUTES (ViewSets)
    # ============================================
    path('', include(router.urls)),
]
