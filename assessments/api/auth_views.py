"""
Authentication Views with OTP Verification.
Provides secure registration, login, and password reset with email OTP.
"""
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse

from assessments.models import AuditLog, UserProfile, OTPToken, PasswordResetToken
from assessments.throttling import AuthRateThrottle, OTPRateThrottle
from assessments.services import NotificationService
from .auth_serializers import (
    UserRegistrationSerializer, LoginSerializer, OTPVerifySerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    ResendOTPSerializer, UserProfileSerializer, ChangePasswordSerializer
)


def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


# =============================================================================
# REGISTRATION
# =============================================================================

@extend_schema(
    tags=['Authentication'],
    summary="Register new user",
    description="""
**Register a new user account with email OTP verification.**

### Flow:
1. Submit registration details
2. Receive 6-digit OTP via email
3. Verify OTP at `/api/auth/verify-otp/` to activate account

### Roles:
- `student` (default) - Can take exams
- `educator` - Can create and manage exams
- `admin` - Full platform access

### Notes:
- Email must be unique
- Password minimum 8 characters
- OTP expires in 10 minutes
""",
    request=UserRegistrationSerializer,
    responses={
        201: OpenApiResponse(
            description="Registration successful, OTP sent",
            examples=[
                OpenApiExample(
                    'Success',
                    value={
                        "message": "Registration successful. Please verify your email with the OTP sent.",
                        "email": "student@example.com",
                        "username": "newstudent",
                        "otp_expires_in": "10 minutes"
                    }
                )
            ]
        ),
        400: OpenApiResponse(description="Validation error")
    }
)
class RegisterView(APIView):
    """Register new user with OTP email verification."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create inactive user
        user = serializer.save()
        user.is_active = False  # Require OTP verification
        user.save()
        
        # Generate and send OTP
        otp, plain_code = OTPToken.create_otp(
            email=user.email,
            purpose=OTPToken.Purpose.EMAIL_VERIFICATION,
            user=user,
            ip_address=get_client_ip(request)
        )
        
        # Send OTP email
        NotificationService.send_otp_email(user, plain_code, 'registration')
        
        AuditLog.log(
            event_type=AuditLog.EventType.LOGIN,
            description=f"New registration: {user.username} (pending verification)",
            request=request,
            user=user
        )
        
        return Response({
            "message": "Registration successful. Please verify your email with the OTP sent.",
            "email": user.email,
            "username": user.username,
            "otp_expires_in": "10 minutes"
        }, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Authentication'],
    summary="Verify OTP and activate account",
    description="""
**Verify the 6-digit OTP sent to your email.**

### Success Response:
- Account activated
- Authentication token returned
- User profile included

### Error Cases:
- Invalid OTP code
- Expired OTP (10 minutes)
- Maximum attempts exceeded (5 attempts)
""",
    request=OTPVerifySerializer,
    responses={
        200: OpenApiResponse(
            description="OTP verified, account activated",
            examples=[
                OpenApiExample(
                    'Success',
                    value={
                        "message": "Email verified successfully.",
                        "token": "abc123def456...",
                        "user": {
                            "id": 1,
                            "username": "newstudent",
                            "email": "student@example.com",
                            "role": "student"
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(description="Invalid or expired OTP")
    }
)
class VerifyOTPView(APIView):
    """Verify OTP to activate account."""
    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        
        success, message, otp = OTPToken.verify_otp(
            email=email,
            code=code,
            purpose=OTPToken.Purpose.EMAIL_VERIFICATION
        )
        
        if not success:
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
        
        # Activate user
        try:
            user = User.objects.get(email=email)
            user.is_active = True
            user.save()
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Generate token
        token, _ = Token.objects.get_or_create(user=user)
        
        AuditLog.log(
            event_type=AuditLog.EventType.LOGIN,
            description=f"Email verified: {user.username}",
            request=request,
            user=user
        )
        
        return Response({
            "message": "Email verified successfully.",
            "token": token.key,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.profile.role if hasattr(user, 'profile') else 'student'
            }
        })


@extend_schema(
    tags=['Authentication'],
    summary="Resend OTP",
    description="""
**Resend OTP to email address.**

Use this if the original OTP expired or wasn't received.
Previous OTPs are invalidated when a new one is sent.

### Rate Limit:
- 3 requests per minute
""",
    request=ResendOTPSerializer,
    responses={
        200: OpenApiResponse(description="OTP resent successfully"),
        400: OpenApiResponse(description="Invalid email or user already verified"),
        429: OpenApiResponse(description="Rate limit exceeded")
    }
)
class ResendOTPView(APIView):
    """Resend OTP for email verification."""
    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        purpose = serializer.validated_data.get('purpose', 'email_verify')
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal if email exists
            return Response({"message": "If the email exists, a new OTP has been sent."})
        
        if purpose == 'email_verify' and user.is_active:
            return Response(
                {"detail": "Account already verified."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        otp_purpose = OTPToken.Purpose.EMAIL_VERIFICATION if purpose == 'email_verify' else OTPToken.Purpose.PASSWORD_RESET
        
        otp, plain_code = OTPToken.create_otp(
            email=email,
            purpose=otp_purpose,
            user=user,
            ip_address=get_client_ip(request)
        )
        
        NotificationService.send_otp_email(user, plain_code, purpose)
        
        return Response({"message": "If the email exists, a new OTP has been sent."})


# =============================================================================
# LOGIN
# =============================================================================

@extend_schema(
    tags=['Authentication'],
    summary="Login",
    description="""
**Authenticate and receive access token.**

### Request:
```json
{
  "username": "student",
  "password": "student123"
}
```

### Response:
Returns authentication token and user profile.
Use the token in subsequent requests:
```
Authorization: Token <your-token>
```

### Demo Accounts:
| Role | Username | Password |
|------|----------|----------|
| Student | student | student123 |
| Educator | educator | educator123 |
| Admin | admin | admin123 |
""",
    request=LoginSerializer,
    responses={
        200: OpenApiResponse(
            description="Login successful",
            examples=[
                OpenApiExample(
                    'Success',
                    value={
                        "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
                        "user": {
                            "id": 1,
                            "username": "student",
                            "email": "student@example.com",
                            "first_name": "Test",
                            "last_name": "Student",
                            "role": "student"
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(description="Invalid credentials"),
        403: OpenApiResponse(description="Account not verified")
    }
)
class LoginView(APIView):
    """Login with username/password to get auth token."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        
        user = authenticate(username=username, password=password)
        
        if not user:
            AuditLog.log(
                event_type=AuditLog.EventType.LOGIN_FAILED,
                description=f"Failed login attempt: {username}",
                request=request
            )
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not user.is_active:
            return Response(
                {"detail": "Account not verified. Please verify your email first."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        token, _ = Token.objects.get_or_create(user=user)
        
        AuditLog.log(
            event_type=AuditLog.EventType.LOGIN,
            description=f"User logged in: {user.username}",
            request=request,
            user=user
        )
        
        return Response({
            "token": token.key,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.profile.role if hasattr(user, 'profile') else 'student'
            }
        })


@extend_schema(tags=['Authentication'])
class LogoutView(APIView):
    """Logout and invalidate token."""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Logout", request=None, responses={200: dict})
    def post(self, request):
        # Delete the token
        try:
            request.user.auth_token.delete()
        except Exception:
            pass
        
        AuditLog.log(
            event_type=AuditLog.EventType.LOGIN,
            description=f"User logged out: {request.user.username}",
            request=request,
            user=request.user
        )
        
        return Response({"message": "Logged out successfully."})


# =============================================================================
# PASSWORD RESET
# =============================================================================

@extend_schema(
    tags=['Authentication'],
    summary="Request password reset",
    description="""
**Request password reset OTP.**

Sends a 6-digit OTP to the registered email address.
For security, always returns success even if email doesn't exist.

### Flow:
1. Request reset (this endpoint)
2. Receive OTP via email
3. Confirm reset at `/api/auth/password-reset/confirm/`
""",
    request=PasswordResetRequestSerializer,
    responses={
        200: OpenApiResponse(
            description="Reset OTP sent (if email exists)",
            examples=[
                OpenApiExample(
                    'Success',
                    value={"message": "If the email exists, a password reset OTP has been sent."}
                )
            ]
        )
    }
)
class PasswordResetRequestView(APIView):
    """Request password reset OTP."""
    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            otp, plain_code = OTPToken.create_otp(
                email=email,
                purpose=OTPToken.Purpose.PASSWORD_RESET,
                user=user,
                ip_address=get_client_ip(request)
            )
            NotificationService.send_otp_email(user, plain_code, 'password_reset')
        except User.DoesNotExist:
            pass  # Don't reveal if email exists
        
        return Response({
            "message": "If the email exists, a password reset OTP has been sent."
        })


@extend_schema(
    tags=['Authentication'],
    summary="Confirm password reset",
    description="""
**Reset password using OTP.**

### Request:
```json
{
  "email": "user@example.com",
  "code": "123456",
  "new_password": "newSecurePassword123",
  "confirm_password": "newSecurePassword123"
}
```

### Password Requirements:
- Minimum 8 characters
- Cannot be too similar to username
- Cannot be a common password
""",
    request=PasswordResetConfirmSerializer,
    responses={
        200: OpenApiResponse(
            description="Password reset successful",
            examples=[
                OpenApiExample('Success', value={"message": "Password reset successful. You can now login."})
            ]
        ),
        400: OpenApiResponse(description="Invalid OTP or password validation failed")
    }
)
class PasswordResetConfirmView(APIView):
    """Confirm password reset with OTP."""
    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        new_password = serializer.validated_data['new_password']
        
        # Verify OTP
        success, message, otp = OTPToken.verify_otp(
            email=email,
            code=code,
            purpose=OTPToken.Purpose.PASSWORD_RESET
        )
        
        if not success:
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update password
        try:
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.save()
            
            # Invalidate all tokens
            Token.objects.filter(user=user).delete()
            
            AuditLog.log(
                event_type=AuditLog.EventType.LOGIN,
                description=f"Password reset completed: {user.username}",
                request=request,
                user=user
            )
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({"message": "Password reset successful. You can now login."})


# =============================================================================
# PROFILE
# =============================================================================

@extend_schema(
    tags=['Authentication'],
    summary="Get current user profile",
    description="""
**Get the authenticated user's profile.**

Returns user details including role and institution.
""",
    responses={
        200: OpenApiResponse(
            description="User profile",
            examples=[
                OpenApiExample(
                    'Success',
                    value={
                        "id": 1,
                        "username": "student",
                        "email": "student@example.com",
                        "first_name": "Test",
                        "last_name": "Student",
                        "role": "student",
                        "institution": "Acad AI University",
                        "department": "Computer Science",
                        "date_joined": "2025-01-01T00:00:00Z"
                    }
                )
            ]
        )
    }
)
class ProfileView(APIView):
    """Get current user profile."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, 'profile', None)
        
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": profile.role if profile else 'student',
            "institution": profile.institution if profile else '',
            "department": profile.department if profile else '',
            "date_joined": user.date_joined
        })


@extend_schema(
    tags=['Authentication'],
    summary="Update user profile",
    description="""
**Update the authenticated user's profile.**

Updatable fields:
- first_name
- last_name
- institution
- department
- bio
""",
    request=UserProfileSerializer,
    responses={200: OpenApiResponse(description="Profile updated")}
)
class ProfileUpdateView(APIView):
    """Update current user profile."""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user
        serializer = UserProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Update user fields
        if 'first_name' in serializer.validated_data:
            user.first_name = serializer.validated_data['first_name']
        if 'last_name' in serializer.validated_data:
            user.last_name = serializer.validated_data['last_name']
        user.save()
        
        # Update profile fields
        profile = user.profile
        if 'institution' in serializer.validated_data:
            profile.institution = serializer.validated_data['institution']
        if 'department' in serializer.validated_data:
            profile.department = serializer.validated_data['department']
        if 'bio' in serializer.validated_data:
            profile.bio = serializer.validated_data['bio']
        profile.save()
        
        return Response({
            "message": "Profile updated successfully.",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": profile.role,
                "institution": profile.institution,
                "department": profile.department
            }
        })


@extend_schema(
    tags=['Authentication'],
    summary="Change password",
    description="""
**Change password for authenticated user.**

Requires current password for verification.
All existing tokens are invalidated after password change.
""",
    request=ChangePasswordSerializer,
    responses={
        200: OpenApiResponse(description="Password changed successfully"),
        400: OpenApiResponse(description="Invalid current password")
    }
)
class ChangePasswordView(APIView):
    """Change password for authenticated user."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        
        if not user.check_password(serializer.validated_data['current_password']):
            return Response(
                {"detail": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        # Invalidate all tokens except current
        Token.objects.filter(user=user).delete()
        new_token, _ = Token.objects.get_or_create(user=user)
        
        AuditLog.log(
            event_type=AuditLog.EventType.LOGIN,
            description=f"Password changed: {user.username}",
            request=request,
            user=user
        )
        
        return Response({
            "message": "Password changed successfully.",
            "token": new_token.key
        })
