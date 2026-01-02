from django.db import models
from django.contrib.auth.models import User


class AuditLog(models.Model):
    class EventType(models.TextChoices):
        LOGIN = 'login', 'User Login'
        LOGOUT = 'logout', 'User Logout'
        LOGIN_FAILED = 'login_failed', 'Failed Login Attempt'
        EXAM_START = 'exam_start', 'Exam Started'
        EXAM_SUBMIT = 'exam_submit', 'Exam Submitted'
        PERMISSION_DENIED = 'permission_denied', 'Permission Denied'
        SUSPICIOUS_ACTIVITY = 'suspicious', 'Suspicious Activity'
        TAB_SWITCH = 'tab_switch', 'Tab Switch Detected'
        COPY_PASTE = 'copy_paste', 'Copy/Paste Attempt'

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    event_type = models.CharField(max_length=30, choices=EventType.choices, db_index=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'event_type']),
            models.Index(fields=['created_at', 'event_type']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.user} - {self.created_at}"

    @classmethod
    def log(cls, event_type, description, request=None, user=None, metadata=None):
        ip_address = None
        user_agent = ''

        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            ip_address = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

            if not user and hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user

        return cls.objects.create(
            user=user,
            event_type=event_type,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {}
        )
