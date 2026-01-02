"""
Certificate Generation Service.
Generates PDF certificates for passed exams.
"""
import io
import hashlib
from datetime import datetime


class CertificateService:
    @staticmethod
    def generate_certificate_data(submission):
        """Generate certificate data for a passed submission."""
        if not submission.passed:
            return None

        cert_id = hashlib.sha256(
            f"{submission.id}-{submission.student.id}-{submission.graded_at}".encode()
        ).hexdigest()[:12].upper()

        return {
            'certificate_id': cert_id,
            'student_name': submission.student.get_full_name() or submission.student.username,
            'student_email': submission.student.email,
            'exam_title': submission.exam.title,
            'course_name': submission.exam.course.name,
            'score': float(submission.percentage),
            'passed': submission.passed,
            'completion_date': submission.graded_at.strftime('%B %d, %Y'),
            'issued_at': datetime.now().isoformat(),
            'verification_url': f"/api/certificates/verify/{cert_id}/"
        }

    @staticmethod
    def generate_certificate_html(cert_data):
        """Generate HTML certificate (can be converted to PDF)."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Georgia', serif; text-align: center; padding: 50px; }}
        .certificate {{ border: 3px solid #1a365d; padding: 40px; max-width: 800px; margin: auto; }}
        .header {{ color: #1a365d; font-size: 36px; margin-bottom: 20px; }}
        .subheader {{ color: #4a5568; font-size: 18px; margin-bottom: 30px; }}
        .name {{ font-size: 32px; color: #2d3748; margin: 20px 0; font-weight: bold; }}
        .course {{ font-size: 24px; color: #1a365d; margin: 15px 0; }}
        .score {{ font-size: 18px; color: #38a169; margin: 10px 0; }}
        .date {{ font-size: 14px; color: #718096; margin-top: 30px; }}
        .cert-id {{ font-size: 12px; color: #a0aec0; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="certificate">
        <div class="header">Certificate of Completion</div>
        <div class="subheader">This is to certify that</div>
        <div class="name">{cert_data['student_name']}</div>
        <div class="subheader">has successfully completed</div>
        <div class="course">{cert_data['exam_title']}</div>
        <div class="subheader">from {cert_data['course_name']}</div>
        <div class="score">Score: {cert_data['score']:.1f}%</div>
        <div class="date">Completed on {cert_data['completion_date']}</div>
        <div class="cert-id">Certificate ID: {cert_data['certificate_id']}</div>
    </div>
</body>
</html>
"""

    @staticmethod
    def verify_certificate(cert_id, submission_id):
        """Verify a certificate is authentic."""
        from assessments.models import Submission
        try:
            submission = Submission.objects.get(id=submission_id)
            expected_id = hashlib.sha256(
                f"{submission.id}-{submission.student.id}-{submission.graded_at}".encode()
            ).hexdigest()[:12].upper()
            return cert_id == expected_id and submission.passed
        except Submission.DoesNotExist:
            return False
