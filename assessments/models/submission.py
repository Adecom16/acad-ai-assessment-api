from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Submission(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        SUBMITTED = 'submitted', 'Submitted'
        GRADING = 'grading', 'Grading'
        GRADED = 'graded', 'Graded'
        FLAGGED = 'flagged', 'Flagged for Review'

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='submissions',
        db_index=True
    )
    exam = models.ForeignKey(
        'Exam',
        on_delete=models.CASCADE,
        related_name='submissions',
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
        db_index=True
    )

    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(null=True)
    attempt_number = models.PositiveIntegerField(default=1)

    # Security tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    browser_fingerprint = models.CharField(max_length=64, blank=True)
    
    # Additional security fields
    ip_changed_during_exam = models.BooleanField(default=False)
    submission_ip = models.GenericIPAddressField(null=True, blank=True)  # IP at submission time
    time_taken_seconds = models.PositiveIntegerField(null=True, blank=True)
    
    # Anti-cheating metrics
    tab_switch_count = models.PositiveIntegerField(default=0)
    focus_lost_count = models.PositiveIntegerField(default=0)
    copy_paste_attempts = models.PositiveIntegerField(default=0)
    right_click_attempts = models.PositiveIntegerField(default=0)
    keyboard_shortcut_attempts = models.PositiveIntegerField(default=0)
    suspicious_activity_flags = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['student', 'exam']),
            models.Index(fields=['student', 'status']),
            models.Index(fields=['exam', 'status']),
            models.Index(fields=['submitted_at']),
            models.Index(fields=['student', 'exam', 'attempt_number']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'exam', 'attempt_number'],
                name='unique_student_exam_attempt'
            )
        ]

    def __str__(self):
        return f"{self.student.username} - {self.exam.title} (Attempt {self.attempt_number})"

    @property
    def is_expired(self):
        if self.status != self.Status.IN_PROGRESS:
            return False
        deadline = self.started_at + timezone.timedelta(minutes=self.exam.duration_minutes)
        return timezone.now() > deadline

    @property
    def is_suspicious(self):
        """
        Determine if submission shows signs of cheating.
        Multiple factors are considered.
        """
        exam = self.exam
        suspicious_reasons = []
        
        # Tab switching beyond limit
        if exam.max_tab_switches > 0 and self.tab_switch_count > exam.max_tab_switches:
            suspicious_reasons.append('excessive_tab_switches')
        
        # Copy-paste when disabled
        if not exam.allow_copy_paste and self.copy_paste_attempts > 0:
            suspicious_reasons.append('copy_paste_attempt')
        
        # IP changed during exam
        if self.ip_changed_during_exam:
            suspicious_reasons.append('ip_address_changed')
        
        # Too many focus lost events
        if self.focus_lost_count > 10:
            suspicious_reasons.append('excessive_focus_lost')
        
        # Suspicious keyboard shortcuts (Ctrl+C, Ctrl+V, etc.)
        if self.keyboard_shortcut_attempts > 5:
            suspicious_reasons.append('suspicious_shortcuts')
        
        # Completed too quickly (less than 20% of allowed time)
        if self.time_taken_seconds and self.exam.duration_minutes:
            min_expected = self.exam.duration_minutes * 60 * 0.1  # 10% of time
            if self.time_taken_seconds < min_expected:
                suspicious_reasons.append('completed_too_quickly')
        
        # Manual flags
        if self.suspicious_activity_flags:
            suspicious_reasons.extend(self.suspicious_activity_flags)
        
        return len(suspicious_reasons) > 0
    
    @property
    def suspicion_score(self):
        """Calculate a suspicion score from 0-100."""
        score = 0
        exam = self.exam
        
        # Tab switches (up to 30 points)
        if exam.max_tab_switches > 0:
            excess = max(0, self.tab_switch_count - exam.max_tab_switches)
            score += min(30, excess * 5)
        
        # Copy-paste (20 points if disabled)
        if not exam.allow_copy_paste and self.copy_paste_attempts > 0:
            score += 20
        
        # IP change (15 points)
        if self.ip_changed_during_exam:
            score += 15
        
        # Focus lost (up to 15 points)
        score += min(15, self.focus_lost_count)
        
        # Manual flags (10 points each)
        score += len(self.suspicious_activity_flags) * 10
        
        # Quick completion (10 points)
        if self.time_taken_seconds and self.exam.duration_minutes:
            min_expected = self.exam.duration_minutes * 60 * 0.1
            if self.time_taken_seconds < min_expected:
                score += 10
        
        return min(100, score)
