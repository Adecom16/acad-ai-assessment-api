"""
Authentication Serializers with validation.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from assessments.models import UserProfile


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration with OTP verification."""
    password = serializers.CharField(
        write_only=True, 
        min_length=8,
        style={'input_type': 'password'},
        help_text="Minimum 8 characters"
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    role = serializers.ChoiceField(
        choices=UserProfile.Role.choices, 
        default='student',
        help_text="User role: student, educator, or admin"
    )
    institution = serializers.CharField(
        required=False, 
        allow_blank=True,
        help_text="Institution or organization name"
    )

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'confirm_password',
            'first_name', 'last_name', 'role', 'institution'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': False},
            'last_name': {'required': False},
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        
        # Validate password strength
        try:
            validate_password(data['password'])
        except ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        
        return data

    def create(self, validated_data):
        role = validated_data.pop('role', 'student')
        institution = validated_data.pop('institution', '')
        validated_data.pop('confirm_password')
        
        user = User.objects.create_user(**validated_data)
        
        # Update profile
        if hasattr(user, 'profile'):
            user.profile.role = role
            user.profile.institution = institution
            user.profile.save()
        
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    username = serializers.CharField(help_text="Username or email")
    password = serializers.CharField(
        style={'input_type': 'password'},
        help_text="Account password"
    )


class OTPVerifySerializer(serializers.Serializer):
    """Serializer for OTP verification."""
    email = serializers.EmailField(help_text="Email address the OTP was sent to")
    code = serializers.CharField(
        min_length=6, 
        max_length=6,
        help_text="6-digit OTP code"
    )

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be numeric.")
        return value


class ResendOTPSerializer(serializers.Serializer):
    """Serializer for resending OTP."""
    email = serializers.EmailField(help_text="Email address to send OTP to")
    purpose = serializers.ChoiceField(
        choices=[('email_verify', 'Email Verification'), ('password_reset', 'Password Reset')],
        default='email_verify',
        help_text="Purpose of OTP"
    )


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request."""
    email = serializers.EmailField(help_text="Registered email address")


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation."""
    email = serializers.EmailField(help_text="Email address")
    code = serializers.CharField(
        min_length=6, 
        max_length=6,
        help_text="6-digit OTP code"
    )
    new_password = serializers.CharField(
        min_length=8,
        style={'input_type': 'password'},
        help_text="New password (min 8 characters)"
    )
    confirm_password = serializers.CharField(
        style={'input_type': 'password'},
        help_text="Confirm new password"
    )

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be numeric.")
        return value

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        
        try:
            validate_password(data['new_password'])
        except ValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        
        return data


class UserProfileSerializer(serializers.Serializer):
    """Serializer for profile updates."""
    first_name = serializers.CharField(required=False, max_length=150)
    last_name = serializers.CharField(required=False, max_length=150)
    institution = serializers.CharField(required=False, max_length=200, allow_blank=True)
    department = serializers.CharField(required=False, max_length=200, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change."""
    current_password = serializers.CharField(
        style={'input_type': 'password'},
        help_text="Current password"
    )
    new_password = serializers.CharField(
        min_length=8,
        style={'input_type': 'password'},
        help_text="New password (min 8 characters)"
    )
    confirm_password = serializers.CharField(
        style={'input_type': 'password'},
        help_text="Confirm new password"
    )

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        
        try:
            validate_password(data['new_password'])
        except ValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        
        return data
