"""
OTP (One-Time Password) Model for secure authentication.
Supports email-based OTP verification for registration and password reset.
"""
import secrets
import hashlib
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class OTPToken(models.Model):
    """
    Secure OTP token for email verification and password reset.
    - 6-digit numeric code for user-friendly input
    - SHA256 hashed storage for security
    - Configurable expiry (default 10 minutes)
    - Rate limiting support via attempt tracking
    """
    
    class Purpose(models.TextChoices):
        EMAIL_VERIFICATION = 'email_verify', 'Email Verification'
        PASSWORD_RESET = 'password_reset', 'Password Reset'
        LOGIN_2FA = 'login_2fa', 'Two-Factor Login'
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_tokens', null=True, blank=True)
    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=64)  # SHA256 hash
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'purpose', 'is_used']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"OTP for {self.email} ({self.get_purpose_display()})"
    
    @classmethod
    def _hash_code(cls, code: str) -> str:
        """Hash OTP code using SHA256."""
        return hashlib.sha256(code.encode()).hexdigest()
    
    @classmethod
    def generate_code(cls) -> str:
        """Generate a 6-digit numeric OTP code."""
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    
    @classmethod
    def create_otp(cls, email: str, purpose: str, user: User = None, 
                   expiry_minutes: int = 10, ip_address: str = None) -> tuple:
        """
        Create a new OTP token.
        Returns (OTPToken instance, plain_code) tuple.
        Invalidates any existing unused OTPs for same email/purpose.
        """
        # Invalidate existing OTPs
        cls.objects.filter(
            email=email, 
            purpose=purpose, 
            is_used=False
        ).update(is_used=True)
        
        # Generate new code
        plain_code = cls.generate_code()
        code_hash = cls._hash_code(plain_code)
        
        otp = cls.objects.create(
            user=user,
            email=email,
            code_hash=code_hash,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
            ip_address=ip_address
        )
        
        return otp, plain_code
    
    @classmethod
    def verify_otp(cls, email: str, code: str, purpose: str) -> tuple:
        """
        Verify an OTP code.
        Returns (success: bool, message: str, otp: OTPToken or None)
        """
        code_hash = cls._hash_code(code)
        
        try:
            otp = cls.objects.get(
                email=email,
                purpose=purpose,
                is_used=False
            )
        except cls.DoesNotExist:
            return False, "Invalid or expired OTP.", None
        except cls.MultipleObjectsReturned:
            # Get the most recent one
            otp = cls.objects.filter(
                email=email,
                purpose=purpose,
                is_used=False
            ).order_by('-created_at').first()
        
        # Check expiry
        if otp.expires_at < timezone.now():
            otp.is_used = True
            otp.save()
            return False, "OTP has expired. Please request a new one.", None
        
        # Check attempts
        if otp.attempts >= otp.max_attempts:
            otp.is_used = True
            otp.save()
            return False, "Maximum attempts exceeded. Please request a new OTP.", None
        
        # Verify code
        if otp.code_hash != code_hash:
            otp.attempts += 1
            otp.save()
            remaining = otp.max_attempts - otp.attempts
            return False, f"Invalid OTP. {remaining} attempts remaining.", None
        
        # Success - mark as used
        otp.is_used = True
        otp.save()
        
        return True, "OTP verified successfully.", otp
    
    @property
    def is_expired(self) -> bool:
        return self.expires_at < timezone.now()
    
    @property
    def is_valid(self) -> bool:
        return not self.is_used and not self.is_expired and self.attempts < self.max_attempts


class PasswordResetToken(models.Model):
    """
    Secure token for password reset flow.
    Uses URL-safe token for reset links.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    @classmethod
    def create_for_user(cls, user: User, ip_address: str = None) -> 'PasswordResetToken':
        """Create a new password reset token for user."""
        # Invalidate existing tokens
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        
        token = secrets.token_urlsafe(32)
        return cls.objects.create(
            user=user,
            token=token,
            expires_at=timezone.now() + timedelta(hours=1),
            ip_address=ip_address
        )
    
    @classmethod
    def get_valid_token(cls, token: str) -> 'PasswordResetToken':
        """Get a valid (unused, not expired) token."""
        try:
            reset_token = cls.objects.get(
                token=token,
                is_used=False,
                expires_at__gt=timezone.now()
            )
            return reset_token
        except cls.DoesNotExist:
            return None
