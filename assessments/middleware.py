"""
Security Middleware for Assessment Platform.
Implements multiple layers of protection against hacking and cheating.
"""
import logging
import hashlib
import time
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """Add security headers to all responses."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Prevent clickjacking
        response['X-Frame-Options'] = 'DENY'
        
        # Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # XSS Protection
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions Policy (disable dangerous features)
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Cache control for sensitive data
        if '/api/' in request.path and request.path not in ['/api/docs/', '/api/redoc/', '/api/schema/']:
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response['Pragma'] = 'no-cache'
        
        # CSP - Skip for API docs
        if not settings.DEBUG or '/api/docs' not in request.path:
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
                "img-src 'self' data: cdn.jsdelivr.net; "
                "frame-ancestors 'none'"
            )
        
        return response


class ExamSessionSecurityMiddleware:
    """
    Enhanced security for exam sessions:
    - IP consistency checking
    - Device fingerprint validation
    - Concurrent session detection
    - Suspicious activity monitoring
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check for suspicious patterns before processing
        if request.user.is_authenticated:
            suspicious = self._check_suspicious_activity(request)
            if suspicious:
                self._log_security_event(request, 'SUSPICIOUS_REQUEST', suspicious)
        
        # Log submission attempts
        if '/submissions/' in request.path and request.method == 'POST':
            self._log_submission_attempt(request)
        
        response = self.get_response(request)
        return response

    def _check_suspicious_activity(self, request) -> str:
        """Check for various suspicious patterns."""
        issues = []
        
        # Check for automated requests (missing common headers)
        if request.method in ['POST', 'PUT', 'PATCH']:
            if not request.META.get('HTTP_USER_AGENT'):
                issues.append('missing_user_agent')
            if not request.META.get('HTTP_ACCEPT'):
                issues.append('missing_accept_header')
        
        # Check for rapid requests from same user
        if self._is_rapid_request(request):
            issues.append('rapid_requests')
        
        return ', '.join(issues) if issues else ''

    def _is_rapid_request(self, request) -> bool:
        """Detect unusually rapid requests (potential automation)."""
        if not request.user.is_authenticated:
            return False
        
        cache_key = f"last_request_{request.user.id}"
        last_request = cache.get(cache_key)
        current_time = time.time()
        
        cache.set(cache_key, current_time, 60)  # Store for 60 seconds
        
        if last_request:
            # Less than 100ms between requests is suspicious
            if current_time - last_request < 0.1:
                return True
        
        return False

    def _log_submission_attempt(self, request):
        """Log all submission attempts for audit."""
        user = request.user if request.user.is_authenticated else 'anonymous'
        ip = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')[:200]
        fingerprint = request.headers.get('X-Browser-Fingerprint', 'none')
        
        logger.info(
            f"SUBMISSION_ATTEMPT | User: {user} | IP: {ip} | "
            f"UA: {user_agent[:50]} | Fingerprint: {fingerprint[:20]}"
        )

    def _log_security_event(self, request, event_type: str, details: str):
        """Log security events."""
        user = request.user if request.user.is_authenticated else 'anonymous'
        ip = self._get_client_ip(request)
        
        logger.warning(
            f"SECURITY_EVENT | Type: {event_type} | User: {user} | "
            f"IP: {ip} | Details: {details} | Path: {request.path}"
        )

    def _get_client_ip(self, request) -> str:
        """Extract client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class IPConsistencyMiddleware:
    """
    Detect IP address changes during active exam sessions.
    Flags submissions if IP changes mid-exam (potential cheating indicator).
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and '/submissions/' in request.path:
            self._check_ip_consistency(request)
        
        return self.get_response(request)

    def _check_ip_consistency(self, request):
        """Check if user's IP has changed during exam session."""
        user_id = request.user.id
        current_ip = self._get_client_ip(request)
        cache_key = f"exam_session_ip_{user_id}"
        
        stored_ip = cache.get(cache_key)
        
        if stored_ip and stored_ip != current_ip:
            # IP changed during session - log it
            logger.warning(
                f"IP_CHANGE_DETECTED | User: {user_id} | "
                f"Original: {stored_ip} | New: {current_ip}"
            )
            
            # Store the flag for the submission
            flag_key = f"ip_change_flag_{user_id}"
            cache.set(flag_key, True, 3600)
        
        # Store/update current IP
        cache.set(cache_key, current_ip, 3600)  # 1 hour

    def _get_client_ip(self, request) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class ConcurrentSessionMiddleware:
    """
    Detect and prevent concurrent exam sessions.
    A student should only have one active exam session at a time.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check on submission creation
        if (request.user.is_authenticated and 
            request.path == '/api/submissions/' and 
            request.method == 'POST'):
            
            if self._has_concurrent_session(request):
                return JsonResponse({
                    'detail': 'You already have an active exam session. Please complete or close it first.'
                }, status=400)
        
        return self.get_response(request)

    def _has_concurrent_session(self, request) -> bool:
        """Check if user has another active exam session."""
        from assessments.models import Submission
        
        active_submissions = Submission.objects.filter(
            student=request.user,
            status='in_progress'
        ).count()
        
        # Allow only one in-progress submission at a time
        return active_submissions >= 1


class RequestValidationMiddleware:
    """
    Validate incoming requests for potential attacks:
    - SQL injection patterns
    - XSS attempts
    - Oversized payloads
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Suspicious patterns
        self.sql_patterns = [
            'union select', 'drop table', 'delete from', 'insert into',
            '1=1', "' or '", '" or "', '--', '/*', '*/', 'xp_'
        ]
        
        self.xss_patterns = [
            '<script', 'javascript:', 'onerror=', 'onload=', 'onclick=',
            'onmouseover=', 'onfocus=', 'eval(', 'document.cookie'
        ]

    def __call__(self, request):
        # Check request body for suspicious patterns
        if request.method in ['POST', 'PUT', 'PATCH']:
            body = request.body.decode('utf-8', errors='ignore').lower()
            
            # Check for SQL injection
            for pattern in self.sql_patterns:
                if pattern in body:
                    logger.warning(
                        f"SQL_INJECTION_ATTEMPT | User: {request.user} | "
                        f"IP: {self._get_client_ip(request)} | Pattern: {pattern}"
                    )
                    return JsonResponse({
                        'detail': 'Invalid request content.'
                    }, status=400)
            
            # Check for XSS
            for pattern in self.xss_patterns:
                if pattern in body:
                    logger.warning(
                        f"XSS_ATTEMPT | User: {request.user} | "
                        f"IP: {self._get_client_ip(request)} | Pattern: {pattern}"
                    )
                    return JsonResponse({
                        'detail': 'Invalid request content.'
                    }, status=400)
        
        return self.get_response(request)

    def _get_client_ip(self, request) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class ExamTimingMiddleware:
    """
    Enforce exam timing rules:
    - Prevent submissions after time expires
    - Detect time manipulation attempts
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check on answer submission
        if (request.user.is_authenticated and 
            '/submit/' in request.path and 
            request.method == 'POST'):
            
            result = self._check_exam_timing(request)
            if result:
                return result
        
        return self.get_response(request)

    def _check_exam_timing(self, request):
        """Verify submission is within allowed time."""
        from assessments.models import Submission
        import re
        
        # Extract submission ID from path
        match = re.search(r'/submissions/(\d+)/submit/', request.path)
        if not match:
            return None
        
        submission_id = match.group(1)
        
        try:
            submission = Submission.objects.select_related('exam').get(
                id=submission_id,
                student=request.user
            )
        except Submission.DoesNotExist:
            return None
        
        # Check if exam time has expired
        if submission.is_expired:
            logger.warning(
                f"LATE_SUBMISSION_ATTEMPT | User: {request.user.id} | "
                f"Submission: {submission_id} | Exam: {submission.exam.title}"
            )
            return JsonResponse({
                'detail': 'Exam time has expired. Your submission cannot be accepted.'
            }, status=400)
        
        return None
