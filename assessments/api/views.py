"""
API Views for Mini Assessment Engine.
Provides endpoints for courses, exams, questions, submissions, and more.
"""
from django.db.models import Sum, Count, Prefetch, Avg
from django.contrib.auth.models import User
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter, 
    OpenApiExample, OpenApiResponse
)

from assessments.models import Course, Exam, Question, Submission, Answer, AuditLog, UserProfile
from assessments.permissions import IsOwnerOrAdmin, IsStaffOrReadOnly, CanSubmitExam, IsEducatorOrAdmin, IsAdminUser
from assessments.throttling import SubmissionRateThrottle
from assessments.grading import get_grading_service
from assessments.services import PlagiarismDetector, ExamAnalytics, ExportService, CertificateService, BulkImportService, NotificationService
from .serializers import (
    CourseSerializer, ExamListSerializer, ExamDetailSerializer, ExamCreateSerializer,
    QuestionSerializer, SubmissionListSerializer, SubmissionDetailSerializer,
    SubmissionCreateSerializer, SubmissionSubmitSerializer,
    UserSerializer, ActivityReportSerializer,
    BulkImportSerializer, AnswerReviewSerializer
)


# =============================================================================
# COURSES
# =============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="List all courses",
        description="Returns a paginated list of all courses. Includes exam count for each course.",
        examples=[
            OpenApiExample(
                'Response Example',
                value={
                    "count": 2,
                    "results": [
                        {"id": 1, "name": "Introduction to Python", "code": "CS101", "exam_count": 3},
                        {"id": 2, "name": "Data Structures", "code": "CS201", "exam_count": 2}
                    ]
                },
                response_only=True
            )
        ]
    ),
    retrieve=extend_schema(
        summary="Get course details",
        description="Returns detailed information about a specific course."
    ),
    create=extend_schema(
        summary="Create new course",
        description="Create a new course. **Requires Educator or Admin role.**",
        examples=[
            OpenApiExample(
                'Request Example',
                value={"name": "Advanced Python", "code": "CS301", "description": "Advanced Python programming concepts"},
                request_only=True
            )
        ]
    ),
    update=extend_schema(
        summary="Update course",
        description="Update an existing course. **Requires Educator or Admin role.**"
    ),
    destroy=extend_schema(
        summary="Delete course",
        description="Delete a course. **Requires Educator or Admin role.**"
    )
)
@extend_schema(tags=['Courses'])
class CourseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing courses.
    
    Courses are the top-level organizational unit containing exams.
    Students have read-only access, while educators can create and manage courses.
    """
    queryset = Course.objects.annotate(exam_count=Count('exams')).order_by('code')
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]
    filterset_fields = ['code']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['code']


# =============================================================================
# EXAMS
# =============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="List exams",
        description="""
Returns a paginated list of exams.

**Students** see only published exams.
**Educators/Admins** see all exams including drafts.
""",
        examples=[
            OpenApiExample(
                'Response Example',
                value={
                    "count": 1,
                    "results": [{
                        "id": 1,
                        "title": "Python Basics Quiz",
                        "course_name": "Introduction to Python",
                        "duration_minutes": 30,
                        "question_count": 10,
                        "status": "published"
                    }]
                },
                response_only=True
            )
        ]
    ),
    retrieve=extend_schema(
        summary="Get exam details",
        description="Returns detailed exam information including questions (without answers for students)."
    ),
    create=extend_schema(
        summary="Create new exam",
        description="Create a new exam in draft status. **Requires Educator or Admin role.**",
        examples=[
            OpenApiExample(
                'Request Example',
                value={
                    "title": "Introduction to Programming",
                    "description": "Test your understanding of basic programming concepts",
                    "course_code": "CS101",
                    "duration_minutes": 60,
                    "passing_score": 70,
                    "max_attempts": 3,
                    "shuffle_questions": True,
                    "show_results_immediately": True,
                    "browser_lockdown": False,
                    "allow_copy_paste": False,
                    "webcam_required": False,
                    "max_tab_switches": 3,
                    "require_enrollment": True,
                    "auto_enroll_course_students": False,
                    "available_from": "2026-01-15T09:00:00Z",
                    "available_until": "2026-01-15T18:00:00Z"
                },
                request_only=True
            )
        ]
    )
)
@extend_schema(tags=['Exams'])
class ExamViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing exams.
    
    Exams contain questions and define assessment parameters like duration,
    passing score, and anti-cheating settings.
    """
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]
    filterset_fields = ['course', 'status']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'created_at', 'duration_minutes']

    def get_queryset(self):
        queryset = Exam.objects.select_related('course', 'created_by').annotate(
            question_count=Count('questions'),
            total_points=Sum('questions__points')
        ).order_by('-created_at')
        
        # Check if user is educator or admin (by role) or Django staff
        user = self.request.user
        is_privileged = user.is_staff or (
            hasattr(user, 'profile') and user.profile.role in ['educator', 'admin']
        )
        
        if not is_privileged:
            queryset = queryset.filter(status=Exam.Status.PUBLISHED)
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return ExamListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return ExamCreateSerializer
        return ExamDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(
        summary="Publish exam",
        description="Publish an exam to make it available to students. Requires at least one question.",
        request=None,
        responses={
            200: OpenApiResponse(
                description="Exam published successfully",
                examples=[OpenApiExample('Success', value={"detail": "Exam published."})]
            ),
            400: OpenApiResponse(description="Cannot publish exam with no questions"),
            403: OpenApiResponse(description="Permission denied")
        }
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def publish(self, request, pk=None):
        # Check if user is educator or admin
        is_privileged = request.user.is_staff or (
            hasattr(request.user, 'profile') and request.user.profile.role in ['educator', 'admin']
        )
        if not is_privileged:
            return Response({"detail": "Educators and admins only."}, status=status.HTTP_403_FORBIDDEN)

        exam = self.get_object()
        if exam.questions.count() == 0:
            return Response({"detail": "Cannot publish exam with no questions."}, status=status.HTTP_400_BAD_REQUEST)

        exam.status = Exam.Status.PUBLISHED
        exam.published_at = timezone.now()
        exam.save()
        
        # Notify enrolled students
        from assessments.models import ExamEnrollment
        enrolled_students = [e.student for e in ExamEnrollment.objects.filter(
            exam=exam, status=ExamEnrollment.Status.ENROLLED
        ).select_related('student')]
        
        if enrolled_students:
            sent = NotificationService.send_exam_published_notification(exam, enrolled_students)
            return Response({"detail": f"Exam published. {sent} students notified."})
        
        return Response({"detail": "Exam published."})

    @extend_schema(
        summary="Get exam analytics",
        description="""
Get comprehensive analytics for an exam including:
- Score distribution and statistics
- Question difficulty index
- Discrimination index
- Pass/fail rates

**Requires Educator or Admin role.**
""",
        tags=['Analytics'],
        responses={
            200: OpenApiResponse(
                description="Analytics data",
                examples=[
                    OpenApiExample(
                        'Response Example',
                        value={
                            "exam_id": 1,
                            "total_submissions": 50,
                            "average_score": 72.5,
                            "pass_rate": 68.0,
                            "score_distribution": {"0-20": 2, "21-40": 5, "41-60": 10, "61-80": 20, "81-100": 13}
                        }
                    )
                ]
            )
        }
    )
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsEducatorOrAdmin])
    def analytics(self, request, pk=None):
        exam = self.get_object()
        analytics = ExamAnalytics(exam)
        return Response(analytics.get_full_analytics())

    @extend_schema(
        summary="Run plagiarism check",
        description="""
Check submissions for potential plagiarism using TF-IDF text similarity.

**Parameters:**
- `threshold` (optional): Similarity threshold (0.0-1.0), default 0.85

**Returns:** List of submission pairs with similarity scores above threshold.
""",
        tags=['Analytics'],
        parameters=[
            OpenApiParameter(name='threshold', type=float, location='query', description='Similarity threshold (0.0-1.0)')
        ]
    )
    @action(detail=True, methods=['get'], url_path='plagiarism-check', permission_classes=[IsAuthenticated, IsEducatorOrAdmin])
    def plagiarism_check(self, request, pk=None):
        exam = self.get_object()
        threshold = float(request.query_params.get('threshold', 0.85))
        
        submissions = Submission.objects.filter(
            exam=exam,
            status__in=[Submission.Status.GRADED, Submission.Status.FLAGGED]
        ).prefetch_related('answers', 'answers__question')
        
        detector = PlagiarismDetector(similarity_threshold=threshold)
        results = detector.check_exam_submissions(submissions)
        results['exam_id'] = exam.id
        results['exam_title'] = exam.title
        results['threshold_used'] = threshold
        
        return Response(results)

    @extend_schema(
        summary="Export exam results (CSV)",
        description="Export exam results to CSV file. **Requires Educator or Admin role.**",
        tags=['Export']
    )
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsEducatorOrAdmin])
    def export(self, request, pk=None):
        exam = self.get_object()
        submissions = Submission.objects.filter(exam=exam).select_related('student').order_by('-submitted_at')
        csv_content = ExportService.export_exam_results(exam, submissions)
        response = HttpResponse(csv_content, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{exam.title}_results.csv"'
        return response

    @extend_schema(
        summary="Export detailed results (CSV)",
        description="Export detailed results with per-question scores. **Requires Educator or Admin role.**",
        tags=['Export']
    )
    @action(detail=True, methods=['get'], url_path='export-detailed', permission_classes=[IsAuthenticated, IsEducatorOrAdmin])
    def export_detailed(self, request, pk=None):
        exam = self.get_object()
        submissions = Submission.objects.filter(
            exam=exam,
            status__in=[Submission.Status.GRADED, Submission.Status.FLAGGED]
        ).select_related('student').prefetch_related('answers')
        csv_content = ExportService.export_detailed_results(exam, submissions)
        response = HttpResponse(csv_content, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{exam.title}_detailed.csv"'
        return response

    @extend_schema(
        summary="Export question analysis (CSV)",
        description="Export question-level analytics. **Requires Educator or Admin role.**",
        tags=['Export']
    )
    @action(detail=True, methods=['get'], url_path='export-analytics', permission_classes=[IsAuthenticated, IsEducatorOrAdmin])
    def export_analytics(self, request, pk=None):
        exam = self.get_object()
        analytics = ExamAnalytics(exam)
        analytics_data = analytics.get_full_analytics()
        csv_content = ExportService.export_question_analysis(analytics_data)
        response = HttpResponse(csv_content, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{exam.title}_question_analysis.csv"'
        return response

    @extend_schema(
        summary="Export plagiarism report (CSV)",
        description="Export plagiarism detection results. **Requires Educator or Admin role.**",
        tags=['Export']
    )
    @action(detail=True, methods=['get'], url_path='export-plagiarism', permission_classes=[IsAuthenticated, IsEducatorOrAdmin])
    def export_plagiarism(self, request, pk=None):
        exam = self.get_object()
        threshold = float(request.query_params.get('threshold', 0.85))
        submissions = Submission.objects.filter(
            exam=exam,
            status__in=[Submission.Status.GRADED, Submission.Status.FLAGGED]
        ).prefetch_related('answers', 'answers__question')
        detector = PlagiarismDetector(similarity_threshold=threshold)
        plagiarism_data = detector.check_exam_submissions(submissions)
        csv_content = ExportService.export_plagiarism_report(plagiarism_data, exam.title)
        response = HttpResponse(csv_content, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{exam.title}_plagiarism_report.csv"'
        return response


# =============================================================================
# QUESTIONS
# =============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="List questions",
        description="""
List questions, optionally filtered by exam.

**Note:** Expected answers and grading rubrics are hidden from students.
""",
        parameters=[
            OpenApiParameter(name='exam', type=int, location='query', description='Filter by exam ID')
        ]
    ),
    retrieve=extend_schema(
        summary="Get question details",
        description="Get detailed question information."
    ),
    create=extend_schema(
        summary="Create question",
        description="""
Add a new question to an exam. **Requires Educator or Admin role.**

**Question Types:**
- `mcq` - Multiple Choice (provide choices array, expected_answer is index)
- `tf` - True/False (choices: ["True", "False"])
- `short` - Short Answer (graded by text similarity)
- `essay` - Essay (graded by rubric matching)
""",
        examples=[
            OpenApiExample(
                'MCQ Example',
                value={
                    "exam": 1,
                    "question_type": "mcq",
                    "text": "What is 2 + 2?",
                    "points": 2,
                    "order": 1,
                    "choices": ["3", "4", "5", "6"],
                    "expected_answer": "1"
                },
                request_only=True
            ),
            OpenApiExample(
                'Short Answer Example',
                value={
                    "exam": 1,
                    "question_type": "short",
                    "text": "What is a Python decorator?",
                    "points": 5,
                    "order": 2,
                    "expected_answer": "A decorator is a function that wraps another function to extend its behavior.",
                    "grading_rubric": "Must mention: function wrapper, extends behavior"
                },
                request_only=True
            )
        ]
    ),
    update=extend_schema(summary="Update question", description="Update an existing question."),
    destroy=extend_schema(summary="Delete question", description="Delete a question.")
)
@extend_schema(tags=['Questions'])
class QuestionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing exam questions.
    
    Supports multiple question types with automated grading.
    """
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]
    filterset_fields = ['exam', 'question_type']

    def get_queryset(self):
        queryset = Question.objects.select_related('exam').order_by('exam_id', 'order')
        exam_id = self.request.query_params.get('exam')
        if exam_id:
            queryset = queryset.filter(exam_id=exam_id)
        return queryset

    @extend_schema(
        summary="Search questions",
        description="""
Search questions by exam title, course code, or question text.

**Query Parameters:**
- `exam_title` - Search by exam title (partial match)
- `course_code` - Filter by course code
- `question_text` - Search in question text
- `question_type` - Filter by type (mcq, tf, short, essay)

Returns question IDs with exam and course info.
""",
        parameters=[
            OpenApiParameter(name='exam_title', type=str, location='query', description='Search by exam title'),
            OpenApiParameter(name='course_code', type=str, location='query', description='Filter by course code'),
            OpenApiParameter(name='question_text', type=str, location='query', description='Search in question text'),
            OpenApiParameter(name='question_type', type=str, location='query', description='Filter by question type'),
        ],
        responses={
            200: OpenApiResponse(
                description="List of questions",
                examples=[
                    OpenApiExample(
                        'Response Example',
                        value={
                            "count": 2,
                            "results": [
                                {
                                    "question_id": 5,
                                    "exam_id": 3,
                                    "exam_title": "Python Basics Quiz",
                                    "course_code": "CS101",
                                    "course_name": "Intro to CS",
                                    "question_type": "mcq",
                                    "question_text": "What is 2+2?",
                                    "points": 2,
                                    "order": 1
                                }
                            ]
                        }
                    )
                ]
            )
        }
    )
    @action(detail=False, methods=['get'])
    def search(self, request):
        exam_title = request.query_params.get('exam_title')
        course_code = request.query_params.get('course_code')
        question_text = request.query_params.get('question_text')
        question_type = request.query_params.get('question_type')

        questions = Question.objects.select_related('exam', 'exam__course').order_by('exam__title', 'order')

        if exam_title:
            questions = questions.filter(exam__title__icontains=exam_title)
        if course_code:
            questions = questions.filter(exam__course__code__iexact=course_code)
        if question_text:
            questions = questions.filter(text__icontains=question_text)
        if question_type:
            questions = questions.filter(question_type=question_type)

        results = []
        for q in questions[:100]:
            results.append({
                'question_id': q.id,
                'exam_id': q.exam.id,
                'exam_title': q.exam.title,
                'course_code': q.exam.course.code,
                'course_name': q.exam.course.name,
                'question_type': q.question_type,
                'question_text': q.text[:100] + '...' if len(q.text) > 100 else q.text,
                'points': float(q.points),
                'order': q.order
            })

        return Response({
            'count': len(results),
            'results': results
        })


# =============================================================================
# SUBMISSIONS
# =============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="List submissions",
        description="""
List exam submissions.

**Students** see only their own submissions.
**Staff** see all submissions.
"""
    ),
    retrieve=extend_schema(
        summary="Get submission details",
        description="Get detailed submission information including answers and grades."
    )
)
@extend_schema(tags=['Submissions'])
class SubmissionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing exam submissions.
    
    Handles the complete exam-taking flow from starting an attempt
    to submitting answers and receiving grades.
    """
    queryset = Submission.objects.none()
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    filterset_fields = ['exam', 'status']
    ordering_fields = ['started_at', 'submitted_at', 'score']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Submission.objects.none()
        
        queryset = Submission.objects.select_related(
            'exam', 'exam__course', 'student'
        ).prefetch_related(
            Prefetch('answers', queryset=Answer.objects.select_related('question').order_by('question__order'))
        )
        if not self.request.user.is_staff:
            queryset = queryset.filter(student=self.request.user)
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return SubmissionListSerializer
        if self.action == 'create':
            return SubmissionCreateSerializer
        return SubmissionDetailSerializer

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

    @extend_schema(
        summary="Start exam attempt",
        description="""
Start a new exam attempt.

**Validations:**
- Exam must be published
- Student must be enrolled (if required)
- Maximum attempts not exceeded
- No in-progress attempt exists

**Returns:** Submission object with exam questions.
""",
        request=SubmissionCreateSerializer,
        examples=[
            OpenApiExample(
                'Request Example',
                value={"exam": 1},
                request_only=True
            )
        ]
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        exam = serializer.validated_data['exam']
        attempt_count = Submission.objects.filter(student=request.user, exam=exam).count()

        submission = Submission.objects.create(
            student=request.user,
            exam=exam,
            attempt_number=attempt_count + 1,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            browser_fingerprint=request.headers.get('X-Browser-Fingerprint', '')
        )

        AuditLog.log(
            event_type=AuditLog.EventType.EXAM_START,
            description=f"Started: {exam.title} (Attempt {attempt_count + 1})",
            request=request,
            user=request.user,
            metadata={'exam_id': exam.id, 'submission_id': submission.id}
        )

        # Notify student that exam has started
        NotificationService.send_exam_started_confirmation(submission)

        return Response(
            SubmissionDetailSerializer(submission, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Submit exam answers",
        description="""
Submit answers for an in-progress exam.

**Process:**
1. Validates all answers belong to exam questions
2. Saves answers
3. Triggers automated grading
4. Returns graded submission

**Anti-Cheating:** Submissions may be flagged if suspicious activity detected.
""",
        request=SubmissionSubmitSerializer,
        responses={200: SubmissionDetailSerializer},
        examples=[
            OpenApiExample(
                'Request Example',
                value={
                    "answers": [
                        {"question_id": 1, "selected_choice": 1},
                        {"question_id": 2, "answer_text": "A decorator wraps a function..."}
                    ]
                },
                request_only=True
            )
        ]
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanSubmitExam], throttle_classes=[SubmissionRateThrottle])
    def submit(self, request, pk=None):
        submission = self.get_object()

        serializer = SubmissionSubmitSerializer(
            data=request.data,
            context={'submission': submission, 'request': request}
        )
        serializer.is_valid(raise_exception=True)

        questions = {q.id: q for q in submission.exam.questions.all()}
        for answer_data in serializer.validated_data['answers']:
            question = questions.get(answer_data['question_id'])
            if question:
                Answer.objects.update_or_create(
                    submission=submission,
                    question=question,
                    defaults={
                        'answer_text': answer_data.get('answer_text', ''),
                        'selected_choice': answer_data.get('selected_choice')
                    }
                )

        submission.status = Submission.Status.SUBMITTED
        submission.submitted_at = timezone.now()
        
        if submission.is_suspicious:
            submission.status = Submission.Status.FLAGGED
        
        submission.save()

        AuditLog.log(
            event_type=AuditLog.EventType.EXAM_SUBMIT,
            description=f"Submitted: {submission.exam.title}",
            request=request,
            user=request.user,
            metadata={
                'exam_id': submission.exam.id,
                'submission_id': submission.id,
                'is_suspicious': submission.is_suspicious
            }
        )

        self._grade_submission(submission)
        submission.refresh_from_db()

        return Response(SubmissionDetailSerializer(submission, context={'request': request}).data)

    @extend_schema(
        summary="Report suspicious activity",
        description="""
Report suspicious activity during exam (anti-cheat).

Called by frontend to report:
- Tab switches
- Focus lost events
- Copy/paste attempts
- Other suspicious flags
""",
        request=ActivityReportSerializer
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanSubmitExam])
    def report_activity(self, request, pk=None):
        submission = self.get_object()
        serializer = ActivityReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        submission.tab_switch_count += data.get('tab_switches', 0)
        submission.focus_lost_count += data.get('focus_lost', 0)
        submission.copy_paste_attempts += data.get('copy_paste_attempts', 0)
        submission.right_click_attempts += data.get('right_click_attempts', 0)
        submission.keyboard_shortcut_attempts += data.get('keyboard_shortcut_attempts', 0)

        flags = data.get('flags', [])
        if flags:
            # Limit flags to prevent abuse
            existing_flags = submission.suspicious_activity_flags or []
            new_flags = [f for f in flags if f not in existing_flags][:10]
            submission.suspicious_activity_flags = existing_flags + new_flags
            
            if new_flags:
                AuditLog.log(
                    event_type=AuditLog.EventType.SUSPICIOUS_ACTIVITY,
                    description=f"Suspicious activity: {', '.join(new_flags)}",
                    request=request,
                    user=request.user,
                    metadata={
                        'submission_id': submission.id,
                        'flags': new_flags,
                        'tab_switches': submission.tab_switch_count,
                        'focus_lost': submission.focus_lost_count
                    }
                )

        submission.save()
        
        # Return current suspicion status
        return Response({
            'status': 'recorded',
            'is_suspicious': submission.is_suspicious,
            'suspicion_score': submission.suspicion_score
        })

    @extend_schema(
        summary="Get my exam results",
        description="Get all submissions for a specific exam by the current user.",
        parameters=[
            OpenApiParameter(name='exam_id', type=int, location='query', required=True, description='Exam ID')
        ]
    )
    @action(detail=False, methods=['get'])
    def my_results(self, request):
        exam_id = request.query_params.get('exam_id')
        if not exam_id:
            return Response({"detail": "exam_id required."}, status=status.HTTP_400_BAD_REQUEST)

        submissions = self.get_queryset().filter(
            student=request.user,
            exam_id=exam_id
        ).order_by('-attempt_number')

        return Response(SubmissionListSerializer(submissions, many=True).data)

    def _grade_submission(self, submission):
        """Grade submission using configured grading service."""
        submission.status = Submission.Status.GRADING
        submission.save()

        grading_service = get_grading_service()
        total_points = 0
        earned_points = 0

        for answer in submission.answers.select_related('question').all():
            question = answer.question
            result = grading_service.grade_answer(
                question_type=question.question_type,
                student_answer=answer.answer_text,
                expected_answer=question.expected_answer,
                max_points=float(question.points),
                choices=question.choices,
                selected_choice=answer.selected_choice,
                grading_rubric=question.grading_rubric
            )

            answer.points_earned = result.points_earned
            answer.is_correct = result.is_correct
            answer.feedback = result.feedback
            answer.grading_method = result.grading_method
            answer.confidence_score = result.confidence
            answer.save()

            total_points += result.max_points
            earned_points += result.points_earned

        submission.score = earned_points
        submission.percentage = (earned_points / total_points * 100) if total_points > 0 else 0
        submission.passed = submission.percentage >= float(submission.exam.passing_score)
        submission.status = Submission.Status.FLAGGED if submission.is_suspicious else Submission.Status.GRADED
        submission.graded_at = timezone.now()
        submission.save()

        # Send notifications
        NotificationService.send_grade_notification(submission)
        NotificationService.send_submission_notification_to_educator(submission)
        
        if submission.is_suspicious:
            NotificationService.send_flagged_submission_alert(submission)
        
        if submission.passed:
            NotificationService.send_certificate_notification(submission)


# =============================================================================
# DASHBOARDS
# =============================================================================

@extend_schema(tags=['Dashboards'])
class AdminDashboardView(APIView):
    """Platform-wide statistics for administrators."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(summary="Admin dashboard statistics", responses={200: dict})
    def get(self, request):
        total_users = User.objects.count()
        users_by_role = UserProfile.objects.values('role').annotate(count=Count('id'))
        
        total_exams = Exam.objects.count()
        published_exams = Exam.objects.filter(status=Exam.Status.PUBLISHED).count()
        
        total_submissions = Submission.objects.count()
        graded_submissions = Submission.objects.filter(status=Submission.Status.GRADED).count()
        flagged_submissions = Submission.objects.filter(status=Submission.Status.FLAGGED).count()
        
        avg_score = Submission.objects.filter(
            status=Submission.Status.GRADED
        ).aggregate(avg=Avg('percentage'))['avg'] or 0
        
        pass_rate = 0
        graded = Submission.objects.filter(status=Submission.Status.GRADED)
        if graded.exists():
            passed = graded.filter(passed=True).count()
            pass_rate = (passed / graded.count()) * 100

        recent_submissions = Submission.objects.select_related(
            'student', 'exam'
        ).order_by('-submitted_at')[:10]
        
        recent_activity = [{
            'id': s.id,
            'student': s.student.username,
            'exam': s.exam.title,
            'status': s.status,
            'score': float(s.percentage) if s.percentage else None,
            'submitted_at': s.submitted_at
        } for s in recent_submissions]

        return Response({
            'users': {
                'total': total_users,
                'by_role': {item['role']: item['count'] for item in users_by_role}
            },
            'exams': {
                'total': total_exams,
                'published': published_exams,
                'draft': total_exams - published_exams
            },
            'submissions': {
                'total': total_submissions,
                'graded': graded_submissions,
                'flagged': flagged_submissions,
                'pending': total_submissions - graded_submissions - flagged_submissions
            },
            'performance': {
                'average_score': round(avg_score, 2),
                'pass_rate': round(pass_rate, 2)
            },
            'recent_activity': recent_activity
        })


@extend_schema(tags=['Dashboards'])
class EducatorDashboardView(APIView):
    """Educator-specific statistics."""
    permission_classes = [IsAuthenticated, IsEducatorOrAdmin]

    @extend_schema(summary="Educator dashboard statistics", responses={200: dict})
    def get(self, request):
        my_exams = Exam.objects.filter(created_by=request.user)
        
        exam_stats = []
        for exam in my_exams.annotate(
            submission_count=Count('submissions'),
            avg_score=Avg('submissions__percentage')
        ):
            passed = exam.submissions.filter(passed=True).count()
            total = exam.submissions.filter(status=Submission.Status.GRADED).count()
            
            exam_stats.append({
                'id': exam.id,
                'title': exam.title,
                'status': exam.status,
                'submissions': exam.submission_count,
                'average_score': round(exam.avg_score or 0, 2),
                'pass_rate': round((passed / total * 100) if total > 0 else 0, 2)
            })

        flagged = Submission.objects.filter(
            exam__created_by=request.user,
            status=Submission.Status.FLAGGED
        ).select_related('student', 'exam')[:10]

        flagged_list = [{
            'id': s.id,
            'student': s.student.username,
            'exam': s.exam.title,
            'flags': s.suspicious_activity_flags,
            'tab_switches': s.tab_switch_count
        } for s in flagged]

        return Response({
            'my_exams': exam_stats,
            'total_exams': my_exams.count(),
            'flagged_submissions': flagged_list
        })


# =============================================================================
# CERTIFICATES
# =============================================================================

@extend_schema(tags=['Certificates'])
class CertificateView(APIView):
    """Generate completion certificates."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get certificate",
        parameters=[OpenApiParameter(name='format', type=str, location='query', description='json or html')],
        responses={200: dict, 400: dict, 403: dict, 404: dict}
    )
    def get(self, request, submission_id):
        try:
            submission = Submission.objects.select_related('exam', 'exam__course', 'student').get(id=submission_id)
        except Submission.DoesNotExist:
            return Response({"detail": "Submission not found."}, status=status.HTTP_404_NOT_FOUND)

        if submission.student != request.user and not request.user.is_staff:
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        if not submission.passed:
            return Response({"detail": "Certificate only available for passed exams."}, status=status.HTTP_400_BAD_REQUEST)

        cert_data = CertificateService.generate_certificate_data(submission)
        
        format_type = request.query_params.get('format', 'json')
        if format_type == 'html':
            html = CertificateService.generate_certificate_html(cert_data)
            return HttpResponse(html, content_type='text/html')
        
        return Response(cert_data)


@extend_schema(tags=['Certificates'])
class CertificateVerifyView(APIView):
    """Verify certificate authenticity."""
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Verify certificate",
        parameters=[OpenApiParameter(name='submission_id', type=int, location='query', required=True)],
        responses={200: dict, 400: dict}
    )
    def get(self, request, cert_id):
        submission_id = request.query_params.get('submission_id')
        if not submission_id:
            return Response({"detail": "submission_id required."}, status=status.HTTP_400_BAD_REQUEST)
        
        is_valid = CertificateService.verify_certificate(cert_id, submission_id)
        return Response({'valid': is_valid, 'certificate_id': cert_id})


# =============================================================================
# BULK IMPORT
# =============================================================================

@extend_schema(tags=['Bulk Import'])
class BulkImportQuestionsView(APIView):
    """Bulk import questions from CSV/JSON file upload."""
    permission_classes = [IsAuthenticated, IsEducatorOrAdmin]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Import questions from file",
        description="""
Upload a CSV or JSON file to bulk import questions into an exam.

**CSV Format:**
```
question_type,text,points,order,choices,expected_answer,grading_rubric
mcq,What is 2+2?,2,1,"[""3"",""4"",""5""]",1,
short,Explain Python decorators,5,2,,A function wrapper,Must mention function
```

**JSON Format:**
```json
[
  {"question_type": "mcq", "text": "What is 2+2?", "points": 2, "choices": ["3","4","5"], "expected_answer": "1"},
  {"question_type": "short", "text": "Explain decorators", "points": 5, "expected_answer": "A function wrapper"}
]
```
""",
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'file': {'type': 'string', 'format': 'binary', 'description': 'CSV or JSON file'},
                    'format': {'type': 'string', 'enum': ['csv', 'json'], 'description': 'File format'}
                },
                'required': ['file', 'format']
            }
        },
        responses={201: dict, 400: dict, 404: dict}
    )
    def post(self, request, exam_id):
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({"detail": "Exam not found."}, status=status.HTTP_404_NOT_FOUND)

        uploaded_file = request.FILES.get('file')
        format_type = request.data.get('format', 'csv')

        if not uploaded_file:
            return Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            content = uploaded_file.read().decode('utf-8')
        except UnicodeDecodeError:
            return Response({"detail": "File must be UTF-8 encoded."}, status=status.HTTP_400_BAD_REQUEST)

        if format_type == 'csv':
            results = BulkImportService.import_questions_csv(exam, content)
        else:
            results = BulkImportService.import_questions_json(exam, content)

        return Response(results, status=status.HTTP_201_CREATED if results['created'] > 0 else status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['Bulk Import'])
class BulkImportTemplateView(APIView):
    """Get import templates."""
    permission_classes = [IsAuthenticated, IsEducatorOrAdmin]

    @extend_schema(
        summary="Get import template",
        parameters=[OpenApiParameter(name='format', type=str, location='query', description='csv or json')],
        responses={200: dict}
    )
    def get(self, request):
        format_type = request.query_params.get('format', 'csv')
        
        if format_type == 'json':
            content = BulkImportService.get_json_template()
            return Response({'template': content, 'format': 'json'})
        
        content = BulkImportService.get_csv_template()
        response = HttpResponse(content, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="question_import_template.csv"'
        return response


# =============================================================================
# GRADE REVIEW
# =============================================================================

@extend_schema(tags=['Grade Review'])
class AnswerReviewView(APIView):
    """Manual grade adjustment."""
    permission_classes = [IsAuthenticated, IsEducatorOrAdmin]

    @extend_schema(summary="Adjust answer grade", request=AnswerReviewSerializer, responses={200: dict, 404: dict})
    def patch(self, request, answer_id):
        try:
            answer = Answer.objects.select_related('question', 'submission', 'submission__student').get(id=answer_id)
        except Answer.DoesNotExist:
            return Response({"detail": "Answer not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AnswerReviewSerializer(data=request.data, context={'answer': answer})
        serializer.is_valid(raise_exception=True)

        old_points = float(answer.points_earned) if answer.points_earned else 0
        new_points = float(serializer.validated_data['points_earned'])
        
        answer.points_earned = new_points
        answer.feedback = serializer.validated_data.get('feedback', answer.feedback)
        answer.grading_method = 'manual_review'
        answer.save()

        submission = answer.submission
        total_earned = sum(a.points_earned or 0 for a in submission.answers.all())
        total_possible = sum(a.question.points for a in submission.answers.all())
        
        submission.score = total_earned
        submission.percentage = (total_earned / total_possible * 100) if total_possible > 0 else 0
        submission.passed = submission.percentage >= float(submission.exam.passing_score)
        submission.save()

        AuditLog.log(
            event_type=AuditLog.EventType.EXAM_SUBMIT,
            description=f"Manual grade adjustment: {old_points} -> {new_points}",
            request=request,
            user=request.user,
            metadata={'answer_id': answer.id, 'submission_id': submission.id}
        )

        # Notify student about grade update
        NotificationService.send_grade_updated_notification(answer, old_points, new_points)

        return Response({
            'answer_id': answer.id,
            'points_earned': float(answer.points_earned),
            'submission_score': float(submission.score),
            'submission_percentage': float(submission.percentage),
            'passed': submission.passed
        })


@extend_schema(tags=['Grade Review'])
class AnswerQueryView(APIView):
    """Query answers for grade review."""
    permission_classes = [IsAuthenticated, IsEducatorOrAdmin]

    @extend_schema(
        summary="Query answers for review",
        description="""
Find answers to review by filtering on student, exam, or course.

**Query Parameters (at least one required):**
- `username` - Student's username
- `exam_id` - Exam ID
- `course_id` - Course ID
- `submission_id` - Specific submission ID

**Returns:** List of answers with student info, question details, and current grades.
""",
        parameters=[
            OpenApiParameter(name='username', type=str, location='query', description='Student username'),
            OpenApiParameter(name='exam_id', type=int, location='query', description='Exam ID'),
            OpenApiParameter(name='course_id', type=int, location='query', description='Course ID'),
            OpenApiParameter(name='submission_id', type=int, location='query', description='Submission ID'),
        ],
        responses={
            200: OpenApiResponse(
                description="List of answers",
                examples=[
                    OpenApiExample(
                        'Response Example',
                        value={
                            "count": 2,
                            "results": [
                                {
                                    "answer_id": 15,
                                    "student_username": "student",
                                    "student_name": "Test Student",
                                    "course_id": 1,
                                    "course_name": "Intro to CS",
                                    "exam_id": 3,
                                    "exam_title": "Python Basics",
                                    "submission_id": 5,
                                    "question_id": 10,
                                    "question_text": "What is a decorator?",
                                    "question_type": "short",
                                    "answer_text": "A function wrapper",
                                    "selected_choice": None,
                                    "points_earned": 3,
                                    "max_points": 5,
                                    "is_correct": False,
                                    "grading_method": "mock_tfidf",
                                    "feedback": "Partial match"
                                }
                            ]
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description="No filter provided")
        }
    )
    def get(self, request):
        username = request.query_params.get('username')
        exam_id = request.query_params.get('exam_id')
        course_id = request.query_params.get('course_id')
        submission_id = request.query_params.get('submission_id')

        if not any([username, exam_id, course_id, submission_id]):
            return Response(
                {"detail": "Provide at least one filter: username, exam_id, course_id, or submission_id"},
                status=status.HTTP_400_BAD_REQUEST
            )

        answers = Answer.objects.select_related(
            'submission', 'submission__student', 'submission__exam', 
            'submission__exam__course', 'question'
        ).order_by('-submission__submitted_at', 'question__order')

        if username:
            answers = answers.filter(submission__student__username__icontains=username)
        if exam_id:
            answers = answers.filter(submission__exam_id=exam_id)
        if course_id:
            answers = answers.filter(submission__exam__course_id=course_id)
        if submission_id:
            answers = answers.filter(submission_id=submission_id)

        # Only show graded/flagged submissions
        answers = answers.filter(
            submission__status__in=[Submission.Status.GRADED, Submission.Status.FLAGGED]
        )

        results = []
        for answer in answers[:100]:  # Limit to 100 results
            results.append({
                'answer_id': answer.id,
                'student_username': answer.submission.student.username,
                'student_name': answer.submission.student.get_full_name() or answer.submission.student.username,
                'course_id': answer.submission.exam.course.id,
                'course_name': answer.submission.exam.course.name,
                'exam_id': answer.submission.exam.id,
                'exam_title': answer.submission.exam.title,
                'submission_id': answer.submission.id,
                'submission_status': answer.submission.status,
                'question_id': answer.question.id,
                'question_text': answer.question.text,
                'question_type': answer.question.question_type,
                'answer_text': answer.answer_text,
                'selected_choice': answer.selected_choice,
                'points_earned': float(answer.points_earned) if answer.points_earned else 0,
                'max_points': float(answer.question.points),
                'is_correct': answer.is_correct,
                'grading_method': answer.grading_method,
                'feedback': answer.feedback
            })

        return Response({
            'count': len(results),
            'results': results
        })


# =============================================================================
# ENROLLMENT
# =============================================================================

from assessments.models import ExamEnrollment, ExamInviteLink
from .serializers import (
    ExamEnrollmentSerializer, EnrollStudentSerializer, 
    ExamInviteLinkSerializer, JoinExamSerializer
)


@extend_schema(tags=['Enrollment'])
class ExamEnrollmentView(APIView):
    """Manage exam enrollments."""
    permission_classes = [IsAuthenticated, IsEducatorOrAdmin]

    @extend_schema(summary="List enrolled students", responses={200: dict, 404: dict})
    def get(self, request, exam_id):
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({"detail": "Exam not found."}, status=status.HTTP_404_NOT_FOUND)

        enrollments = ExamEnrollment.objects.filter(exam=exam).select_related('student', 'exam')
        return Response({
            'exam_id': exam.id,
            'exam_title': exam.title,
            'require_enrollment': exam.require_enrollment,
            'total_enrolled': enrollments.count(),
            'enrollments': ExamEnrollmentSerializer(enrollments, many=True).data
        })

    @extend_schema(summary="Enroll students", request=EnrollStudentSerializer, responses={201: dict, 400: dict})
    def post(self, request, exam_id):
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({"detail": "Exam not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = EnrollStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        enrolled = []
        errors = []
        send_invitation = serializer.validated_data.get('send_invitation', True)

        for student_id in serializer.validated_data.get('student_ids', []):
            try:
                student = User.objects.get(id=student_id)
                enrollment, created = ExamEnrollment.objects.get_or_create(
                    exam=exam,
                    student=student,
                    defaults={'enrolled_by': request.user, 'status': ExamEnrollment.Status.ENROLLED}
                )
                if created:
                    enrolled.append({'id': student.id, 'username': student.username})
                    if send_invitation:
                        NotificationService.send_exam_invitation(enrollment)
            except User.DoesNotExist:
                errors.append(f"User ID {student_id} not found")

        for email in serializer.validated_data.get('student_emails', []):
            try:
                student = User.objects.get(email=email)
                enrollment, created = ExamEnrollment.objects.get_or_create(
                    exam=exam,
                    student=student,
                    defaults={'enrolled_by': request.user, 'status': ExamEnrollment.Status.ENROLLED}
                )
                if created:
                    enrolled.append({'id': student.id, 'email': email})
                    if send_invitation:
                        NotificationService.send_exam_invitation(enrollment)
            except User.DoesNotExist:
                errors.append(f"User with email {email} not found")

        return Response({
            'enrolled': len(enrolled),
            'students': enrolled,
            'errors': errors
        }, status=status.HTTP_201_CREATED if enrolled else status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['Enrollment'])
class ExamEnrollmentDetailView(APIView):
    """Manage individual enrollment."""
    permission_classes = [IsAuthenticated, IsEducatorOrAdmin]

    @extend_schema(
        summary="Update enrollment status",
        request={'type': 'object', 'properties': {'status': {'type': 'string', 'enum': ['enrolled', 'pending', 'revoked']}}},
        responses={200: ExamEnrollmentSerializer, 404: dict},
        examples=[
            OpenApiExample('Request Example', value={'status': 'enrolled'}, request_only=True)
        ]
    )
    def patch(self, request, enrollment_id):
        try:
            enrollment = ExamEnrollment.objects.get(id=enrollment_id)
        except ExamEnrollment.DoesNotExist:
            return Response({"detail": "Enrollment not found."}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        if new_status and new_status in dict(ExamEnrollment.Status.choices):
            enrollment.status = new_status
            enrollment.save()
            if new_status == ExamEnrollment.Status.ENROLLED:
                NotificationService.send_enrollment_confirmation(enrollment)

        return Response(ExamEnrollmentSerializer(enrollment).data)

    @extend_schema(summary="Revoke enrollment", request=None, responses={200: dict, 404: dict})
    def delete(self, request, enrollment_id):
        try:
            enrollment = ExamEnrollment.objects.get(id=enrollment_id)
        except ExamEnrollment.DoesNotExist:
            return Response({"detail": "Enrollment not found."}, status=status.HTTP_404_NOT_FOUND)

        enrollment.status = ExamEnrollment.Status.REVOKED
        enrollment.save()
        return Response({"detail": "Enrollment revoked."})


@extend_schema(tags=['Enrollment'])
class ExamInviteLinkView(APIView):
    """Manage exam invite links."""
    permission_classes = [IsAuthenticated, IsEducatorOrAdmin]

    @extend_schema(summary="List invite links", responses={200: ExamInviteLinkSerializer(many=True), 404: dict})
    def get(self, request, exam_id):
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({"detail": "Exam not found."}, status=status.HTTP_404_NOT_FOUND)

        links = ExamInviteLink.objects.filter(exam=exam, is_active=True)
        return Response(ExamInviteLinkSerializer(links, many=True).data)

    @extend_schema(summary="Create invite link", request=ExamInviteLinkSerializer, responses={201: ExamInviteLinkSerializer, 404: dict})
    def post(self, request, exam_id):
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({"detail": "Exam not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ExamInviteLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        link = ExamInviteLink.objects.create(
            exam=exam,
            created_by=request.user,
            expires_at=serializer.validated_data.get('expires_at'),
            max_uses=serializer.validated_data.get('max_uses'),
            requires_approval=serializer.validated_data.get('requires_approval', False)
        )

        return Response(ExamInviteLinkSerializer(link).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Enrollment'])
class ExamInviteLinkDetailView(APIView):
    """Manage individual invite link."""
    permission_classes = [IsAuthenticated, IsEducatorOrAdmin]

    @extend_schema(summary="Deactivate invite link", request=None, responses={200: dict, 404: dict})
    def delete(self, request, link_id):
        try:
            link = ExamInviteLink.objects.get(id=link_id)
        except ExamInviteLink.DoesNotExist:
            return Response({"detail": "Link not found."}, status=status.HTTP_404_NOT_FOUND)

        link.is_active = False
        link.save()
        return Response({"detail": "Invite link deactivated."})


@extend_schema(tags=['Enrollment'])
class JoinExamView(APIView):
    """Join exam via invite code."""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Join exam with invite code", request=JoinExamSerializer, responses={201: dict, 400: dict})
    def post(self, request):
        serializer = JoinExamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data['code']
        link = ExamInviteLink.get_by_code(code)

        if not link:
            return Response({"detail": "Invalid or expired invite code."}, status=status.HTTP_400_BAD_REQUEST)

        if hasattr(request.user, 'profile') and request.user.profile.role not in ['student', 'educator', 'admin']:
            return Response({"detail": "Only students can join exams."}, status=status.HTTP_403_FORBIDDEN)

        enrollment = link.use(request.user)
        
        if not enrollment:
            return Response({"detail": "Could not enroll. Link may be expired or at capacity."}, status=status.HTTP_400_BAD_REQUEST)

        if enrollment.status == ExamEnrollment.Status.ENROLLED:
            NotificationService.send_enrollment_confirmation(enrollment)
            # Notify educator about new enrollment
            NotificationService.send_new_enrollment_notification(enrollment)

        return Response({
            'message': 'Enrollment pending approval' if link.requires_approval else 'Successfully enrolled',
            'enrollment': ExamEnrollmentSerializer(enrollment).data
        }, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Enrollment'])
class MyEnrollmentsView(APIView):
    """View own enrollments."""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List my enrollments", responses={200: dict})
    def get(self, request):
        enrollments = ExamEnrollment.objects.filter(
            student=request.user
        ).select_related('exam', 'exam__course')

        data = []
        for e in enrollments:
            data.append({
                'id': e.id,
                'exam_id': e.exam.id,
                'exam_title': e.exam.title,
                'course': e.exam.course.name,
                'status': e.status,
                'enrolled_at': e.enrolled_at,
                'exam_status': e.exam.status,
                'is_available': e.exam.is_available,
                'duration_minutes': e.exam.duration_minutes
            })

        return Response(data)


# =============================================================================
# LEADERBOARD
# =============================================================================

from assessments.services import LeaderboardService


@extend_schema(tags=['Leaderboard'])
class ExamLeaderboardView(APIView):
    """Exam leaderboard with rankings."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get exam leaderboard",
        description="""
Get the leaderboard for a specific exam showing top performers.

**Features:**
- Ranked by score percentage
- Shows percentile ranking
- Includes exam statistics

**Query Parameters:**
- `limit`: Number of results (default: 50, max: 100)
""",
        parameters=[
            OpenApiParameter(name='limit', type=int, location='query', description='Number of results')
        ],
        responses={
            200: OpenApiResponse(
                description="Leaderboard data",
                examples=[
                    OpenApiExample(
                        'Response Example',
                        value={
                            "exam_id": 1,
                            "leaderboard": [
                                {
                                    "rank": 1,
                                    "student_name": "John Doe",
                                    "percentage": 95.5,
                                    "percentile": 99.0,
                                    "passed": True
                                }
                            ],
                            "statistics": {
                                "total_submissions": 50,
                                "average_score": 72.5,
                                "pass_rate": 68.0
                            }
                        }
                    )
                ]
            )
        }
    )
    def get(self, request, exam_id):
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({"detail": "Exam not found."}, status=status.HTTP_404_NOT_FOUND)
        
        limit = min(int(request.query_params.get('limit', 50)), 100)
        data = LeaderboardService.get_exam_leaderboard(exam_id, limit)
        data['exam_title'] = exam.title
        
        return Response(data)


@extend_schema(tags=['Leaderboard'])
class StudentRankingView(APIView):
    """Get student's ranking in an exam."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get my ranking",
        description="Get the current user's ranking in a specific exam.",
        responses={200: dict, 404: dict}
    )
    def get(self, request, exam_id):
        data = LeaderboardService.get_student_ranking(request.user.id, exam_id)
        
        if 'error' in data:
            return Response({"detail": data['error']}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(data)


@extend_schema(tags=['Leaderboard'])
class CourseLeaderboardView(APIView):
    """Course-wide leaderboard."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get course leaderboard",
        description="Get overall leaderboard for a course across all exams.",
        responses={200: dict, 404: dict}
    )
    def get(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({"detail": "Course not found."}, status=status.HTTP_404_NOT_FOUND)
        
        limit = min(int(request.query_params.get('limit', 20)), 50)
        data = LeaderboardService.get_course_leaderboard(course_id, limit)
        data['course_name'] = course.name
        
        return Response(data)


@extend_schema(tags=['Leaderboard'])
class TrendingPerformersView(APIView):
    """Trending performers based on recent improvement."""
    permission_classes = [IsAuthenticated, IsEducatorOrAdmin]

    @extend_schema(
        summary="Get trending performers",
        description="Get students showing the most improvement in recent days.",
        parameters=[
            OpenApiParameter(name='days', type=int, location='query', description='Period in days (default: 7)')
        ],
        responses={200: dict}
    )
    def get(self, request):
        days = min(int(request.query_params.get('days', 7)), 30)
        data = LeaderboardService.get_trending_performers(days)
        return Response(data)


# =============================================================================
# STUDENT PROGRESS
# =============================================================================

@extend_schema(tags=['Analytics'])
class StudentProgressView(APIView):
    """Student's personal progress and statistics."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get my progress",
        description="Get comprehensive progress statistics for the current user.",
        responses={200: dict}
    )
    def get(self, request):
        user = request.user
        
        # Overall stats
        submissions = Submission.objects.filter(
            student=user,
            status=Submission.Status.GRADED
        )
        
        overall_stats = submissions.aggregate(
            total_exams=Count('exam', distinct=True),
            total_submissions=Count('id'),
            avg_score=Avg('percentage'),
            total_passed=Count('id', filter=models.Q(passed=True))
        )
        
        # Recent submissions
        recent = submissions.select_related('exam', 'exam__course').order_by('-submitted_at')[:10]
        recent_list = [{
            'exam_id': s.exam.id,
            'exam_title': s.exam.title,
            'course': s.exam.course.name,
            'score': float(s.percentage) if s.percentage else 0,
            'passed': s.passed,
            'submitted_at': s.submitted_at
        } for s in recent]
        
        # Performance by course
        by_course = submissions.values(
            'exam__course__id', 'exam__course__name'
        ).annotate(
            avg_score=Avg('percentage'),
            exams_taken=Count('exam', distinct=True),
            submissions=Count('id')
        ).order_by('-avg_score')
        
        course_stats = [{
            'course_id': c['exam__course__id'],
            'course_name': c['exam__course__name'],
            'average_score': round(c['avg_score'] or 0, 2),
            'exams_taken': c['exams_taken'],
            'submissions': c['submissions']
        } for c in by_course]
        
        return Response({
            'user_id': user.id,
            'username': user.username,
            'overall': {
                'exams_taken': overall_stats['total_exams'] or 0,
                'total_submissions': overall_stats['total_submissions'] or 0,
                'average_score': round(overall_stats['avg_score'] or 0, 2),
                'pass_rate': round(
                    (overall_stats['total_passed'] / overall_stats['total_submissions'] * 100)
                    if overall_stats['total_submissions'] else 0, 2
                )
            },
            'recent_submissions': recent_list,
            'by_course': course_stats
        })


# Need to import models for the Q object
from django.db import models
