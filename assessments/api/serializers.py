from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from assessments.models import Course, Exam, Question, Submission, Answer, UserProfile


class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='profile.role', read_only=True)
    institution = serializers.CharField(source='profile.institution', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'institution']
        read_only_fields = fields


class CourseSerializer(serializers.ModelSerializer):
    exam_count = serializers.IntegerField(read_only=True, source='exams.count')

    class Meta:
        model = Course
        fields = ['id', 'name', 'code', 'description', 'exam_count', 'created_at']
        read_only_fields = ['created_at']


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            'id', 'exam', 'question_type', 'text', 'points', 'order',
            'choices', 'expected_answer', 'grading_rubric'
        ]
        read_only_fields = ['id']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        # Check user role instead of is_staff
        is_privileged = False
        if request and request.user.is_authenticated:
            is_privileged = request.user.is_staff or (
                hasattr(request.user, 'profile') and 
                request.user.profile.role in ['educator', 'admin']
            )
        if not is_privileged:
            data.pop('expected_answer', None)
            data.pop('grading_rubric', None)
        return data


class QuestionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'question_type', 'text', 'points', 'order', 'choices']


class ExamListSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name', read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    total_points = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)

    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'description', 'course', 'course_name', 'course_code',
            'duration_minutes', 'passing_score', 'max_attempts', 'status',
            'question_count', 'total_points', 'browser_lockdown', 'allow_copy_paste',
            'max_tab_switches', 'created_at'
        ]


class ExamCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating exams - only writable fields."""
    course_code = serializers.SlugRelatedField(
        queryset=Course.objects.all(),
        slug_field='code',
        source='course'
    )

    class Meta:
        model = Exam
        fields = [
            'title', 'description', 'course_code',
            'duration_minutes', 'passing_score', 'max_attempts',
            'shuffle_questions', 'show_results_immediately',
            'browser_lockdown', 'allow_copy_paste', 'webcam_required', 'max_tab_switches',
            'require_enrollment', 'auto_enroll_course_students',
            'available_from', 'available_until'
        ]


class ExamDetailSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(),
        source='course',
        write_only=True
    )
    questions = QuestionListSerializer(many=True, read_only=True)
    created_by = UserSerializer(read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    total_points = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)

    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'description', 'course', 'course_id',
            'duration_minutes', 'passing_score', 'max_attempts', 'status',
            'shuffle_questions', 'show_results_immediately',
            'browser_lockdown', 'allow_copy_paste', 'webcam_required', 'max_tab_switches',
            'require_enrollment', 'auto_enroll_course_students',
            'available_from', 'available_until',
            'questions', 'question_count', 'total_points',
            'created_by', 'created_at', 'updated_at', 'published_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'published_at', 'status']


class AnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.text', read_only=True)
    question_type = serializers.CharField(source='question.question_type', read_only=True)
    max_points = serializers.DecimalField(source='question.points', max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = Answer
        fields = [
            'id', 'question', 'question_text', 'question_type',
            'answer_text', 'selected_choice',
            'points_earned', 'max_points', 'is_correct', 'feedback',
            'grading_method', 'confidence_score', 'answered_at'
        ]
        read_only_fields = [
            'points_earned', 'is_correct', 'feedback',
            'grading_method', 'confidence_score', 'answered_at'
        ]


class AnswerSubmitSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    answer_text = serializers.CharField(required=False, allow_blank=True, default='')
    selected_choice = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        if not data.get('answer_text') and data.get('selected_choice') is None:
            raise serializers.ValidationError("Either answer_text or selected_choice must be provided")
        return data


class SubmissionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = ['exam']

    def validate_exam(self, exam):
        user = self.context['request'].user

        if exam.status != Exam.Status.PUBLISHED:
            raise serializers.ValidationError("This exam is not available.")

        # Check enrollment if required
        if exam.require_enrollment and not exam.is_student_enrolled(user):
            raise serializers.ValidationError("You are not enrolled in this exam.")

        attempt_count = Submission.objects.filter(
            student=user,
            exam=exam,
            status__in=[Submission.Status.SUBMITTED, Submission.Status.GRADED]
        ).count()

        if attempt_count >= exam.max_attempts:
            raise serializers.ValidationError(f"Maximum attempts ({exam.max_attempts}) reached.")

        in_progress = Submission.objects.filter(
            student=user,
            exam=exam,
            status=Submission.Status.IN_PROGRESS
        ).first()

        if in_progress and not in_progress.is_expired:
            raise serializers.ValidationError("You have an in-progress attempt for this exam.")

        return exam


class SubmissionSubmitSerializer(serializers.Serializer):
    answers = AnswerSubmitSerializer(many=True)

    def validate_answers(self, answers):
        submission = self.context.get('submission')
        if not submission:
            return answers

        exam_question_ids = set(submission.exam.questions.values_list('id', flat=True))
        submitted_ids = set()

        for answer in answers:
            qid = answer['question_id']
            if qid not in exam_question_ids:
                raise serializers.ValidationError(f"Question {qid} does not belong to this exam.")
            if qid in submitted_ids:
                raise serializers.ValidationError(f"Duplicate answer for question {qid}.")
            submitted_ids.add(qid)

        return answers


class SubmissionListSerializer(serializers.ModelSerializer):
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    is_suspicious = serializers.BooleanField(read_only=True)

    class Meta:
        model = Submission
        fields = [
            'id', 'exam', 'exam_title', 'student_name', 'status',
            'score', 'percentage', 'passed', 'attempt_number',
            'is_suspicious', 'tab_switch_count', 'started_at', 'submitted_at', 'graded_at'
        ]


class SubmissionDetailSerializer(serializers.ModelSerializer):
    exam = ExamListSerializer(read_only=True)
    student = UserSerializer(read_only=True)
    answers = AnswerSerializer(many=True, read_only=True)
    time_remaining = serializers.SerializerMethodField()
    is_suspicious = serializers.BooleanField(read_only=True)

    class Meta:
        model = Submission
        fields = [
            'id', 'exam', 'student', 'status',
            'started_at', 'submitted_at', 'graded_at',
            'score', 'percentage', 'passed', 'attempt_number',
            'tab_switch_count', 'focus_lost_count', 'copy_paste_attempts',
            'is_suspicious', 'suspicious_activity_flags',
            'answers', 'time_remaining'
        ]

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_time_remaining(self, obj) -> int | None:
        if obj.status != Submission.Status.IN_PROGRESS:
            return None
        deadline = obj.started_at + timezone.timedelta(minutes=obj.exam.duration_minutes)
        remaining = deadline - timezone.now()
        return max(0, int(remaining.total_seconds()))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not instance.exam.show_results_immediately and instance.status != Submission.Status.GRADED:
            for answer in data.get('answers', []):
                answer['is_correct'] = None
                answer['feedback'] = None
                answer['points_earned'] = None
        return data


class ActivityReportSerializer(serializers.Serializer):
    """Serializer for reporting suspicious activity during exam."""
    tab_switches = serializers.IntegerField(min_value=0, default=0)
    focus_lost = serializers.IntegerField(min_value=0, default=0)
    copy_paste_attempts = serializers.IntegerField(min_value=0, default=0)
    right_click_attempts = serializers.IntegerField(min_value=0, default=0)
    keyboard_shortcut_attempts = serializers.IntegerField(min_value=0, default=0)
    flags = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
        help_text="List of suspicious activity flags"
    )


# Bulk Import Serializers
class BulkImportSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="CSV or JSON file containing questions")
    format = serializers.ChoiceField(
        choices=['csv', 'json'],
        help_text="File format: csv or json"
    )


# Answer Review Serializer (for manual grade adjustment)
class AnswerReviewSerializer(serializers.Serializer):
    points_earned = serializers.DecimalField(max_digits=5, decimal_places=2)
    feedback = serializers.CharField(required=False, allow_blank=True)
    
    def validate_points_earned(self, value):
        answer = self.context.get('answer')
        if answer and value > answer.question.points:
            raise serializers.ValidationError(f"Cannot exceed max points ({answer.question.points})")
        return value


# Enrollment Serializers
class ExamEnrollmentSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    exam_id = serializers.IntegerField(source='exam.id', read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    student_id = serializers.IntegerField(source='student.id', read_only=True)
    student_username = serializers.CharField(source='student.username', read_only=True)
    student_email = serializers.CharField(source='student.email', read_only=True)
    status = serializers.CharField(read_only=True)
    enrolled_at = serializers.DateTimeField(read_only=True)
    invitation_email_sent = serializers.BooleanField(read_only=True)


class EnrollStudentSerializer(serializers.Serializer):
    student_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of student user IDs to enroll"
    )
    student_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        help_text="List of student emails to enroll"
    )
    send_invitation = serializers.BooleanField(default=True)

    def validate(self, data):
        if not data.get('student_ids') and not data.get('student_emails'):
            raise serializers.ValidationError("Provide either student_ids or student_emails")
        return data


class ExamInviteLinkSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(read_only=True)
    exam_id = serializers.IntegerField(source='exam.id', read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    max_uses = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    use_count = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(default=True)
    requires_approval = serializers.BooleanField(default=False)
    created_at = serializers.DateTimeField(read_only=True)
    invite_url = serializers.SerializerMethodField()

    def get_invite_url(self, obj) -> str:
        from django.conf import settings
        base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:8000')
        return f"{base_url}/join/{obj.code}"


class JoinExamSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
