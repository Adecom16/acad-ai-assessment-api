from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Exam(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    course = models.ForeignKey(
        'Course',
        on_delete=models.CASCADE,
        related_name='exams',
        db_index=True
    )
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(480)]
    )
    passing_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=60.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    max_attempts = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True
    )
    shuffle_questions = models.BooleanField(default=False)
    show_results_immediately = models.BooleanField(default=True)
    
    # Anti-cheating settings
    browser_lockdown = models.BooleanField(default=False)
    allow_copy_paste = models.BooleanField(default=True)
    webcam_required = models.BooleanField(default=False)
    max_tab_switches = models.PositiveIntegerField(default=0)  # 0 = unlimited

    # Scheduling
    available_from = models.DateTimeField(null=True, blank=True, help_text="When exam becomes available")
    available_until = models.DateTimeField(null=True, blank=True, help_text="When exam closes")

    # Enrollment settings
    require_enrollment = models.BooleanField(default=True, help_text="If True, only enrolled students can take exam")
    auto_enroll_course_students = models.BooleanField(default=False, help_text="Auto-enroll all course students")

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_exams'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'course']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.title

    def get_total_points(self):
        return self.questions.aggregate(total=models.Sum('points'))['total'] or 0

    def get_question_count(self):
        return self.questions.count()

    @property
    def is_available(self):
        """Check if exam is currently available based on schedule."""
        from django.utils import timezone
        now = timezone.now()
        if self.status != self.Status.PUBLISHED:
            return False
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now > self.available_until:
            return False
        return True

    def is_student_enrolled(self, user):
        """Check if a student is enrolled in this exam."""
        if not self.require_enrollment:
            return True
        return self.enrollments.filter(
            student=user, 
            status__in=['enrolled', 'completed']
        ).exists()

    def get_enrolled_students(self):
        """Get all enrolled students."""
        return User.objects.filter(
            exam_enrollments__exam=self,
            exam_enrollments__status__in=['enrolled', 'completed']
        )
