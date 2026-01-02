"""Exam Enrollment model for controlling student access to exams."""
import secrets
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ExamEnrollment(models.Model):
    """Tracks which students are enrolled in which exams."""
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ENROLLED = 'enrolled', 'Enrolled'
        COMPLETED = 'completed', 'Completed'
        REVOKED = 'revoked', 'Revoked'

    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, related_name='enrollments')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_enrollments')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ENROLLED)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    enrolled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, 
        related_name='enrollments_created'
    )
    invitation_email_sent = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['exam', 'student']
        ordering = ['-enrolled_at']

    def __str__(self):
        return f"{self.student.username} - {self.exam.title}"


class ExamInviteLink(models.Model):
    """Shareable invite links for exam enrollment."""
    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, related_name='invite_links')
    code = models.CharField(max_length=32, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank for unlimited")
    use_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Invite for {self.exam.title} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = secrets.token_urlsafe(16)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.max_uses and self.use_count >= self.max_uses:
            return False
        return True

    def use(self, student, enrolled_by=None):
        """Use this invite link to enroll a student."""
        if not self.is_valid:
            return None
        
        enrollment, created = ExamEnrollment.objects.get_or_create(
            exam=self.exam,
            student=student,
            defaults={
                'status': ExamEnrollment.Status.PENDING if self.requires_approval else ExamEnrollment.Status.ENROLLED,
                'enrolled_by': enrolled_by or self.created_by
            }
        )
        
        if created:
            self.use_count += 1
            self.save(update_fields=['use_count'])
        
        return enrollment

    @classmethod
    def get_by_code(cls, code):
        try:
            link = cls.objects.select_related('exam').get(code=code)
            return link if link.is_valid else None
        except cls.DoesNotExist:
            return None
