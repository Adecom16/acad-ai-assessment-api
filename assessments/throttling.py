from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class SubmissionRateThrottle(UserRateThrottle):
    """Strict rate limit for exam submissions to prevent abuse."""
    scope = 'submission'
    rate = '10/minute'


class BurstRateThrottle(UserRateThrottle):
    """General burst protection for authenticated users."""
    scope = 'burst'
    rate = '60/minute'


class AuthRateThrottle(AnonRateThrottle):
    """Rate limit for authentication endpoints to prevent brute force."""
    scope = 'auth'
    rate = '5/minute'


class OTPRateThrottle(AnonRateThrottle):
    """Strict rate limit for OTP requests to prevent abuse."""
    scope = 'otp'
    rate = '3/minute'
