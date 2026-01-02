"""
Notification Service for email notifications using Google SMTP.
"""
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    FROM_EMAIL = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@assessment.local')

    @classmethod
    def _send_email(cls, subject, message, recipient_list, html_message=None):
        """Base email sending method."""
        try:
            if html_message:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=message,
                    from_email=cls.FROM_EMAIL,
                    to=recipient_list
                )
                email.attach_alternative(html_message, "text/html")
                email.send(fail_silently=False)
            else:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=cls.FROM_EMAIL,
                    recipient_list=recipient_list,
                    fail_silently=False
                )
            logger.info(f"Email sent to {recipient_list}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Email send failed to {recipient_list}: {e}")
            return False

    # =========================================================================
    # STUDENT NOTIFICATIONS
    # =========================================================================

    @classmethod
    def send_exam_invitation(cls, enrollment, invite_link=None):
        """Send exam invitation email to student."""
        student = enrollment.student
        exam = enrollment.exam
        
        if not student.email:
            return False

        subject = f"You're invited to take: {exam.title}"
        
        message = f"""
Hello {student.get_full_name() or student.username},

You have been invited to take the following exam:

Exam: {exam.title}
Course: {exam.course.name}
Duration: {exam.duration_minutes} minutes
Passing Score: {exam.passing_score}%
"""
        if exam.available_from:
            message += f"Available from: {exam.available_from.strftime('%Y-%m-%d %H:%M')}\n"
        if exam.available_until:
            message += f"Available until: {exam.available_until.strftime('%Y-%m-%d %H:%M')}\n"

        if invite_link:
            message += f"\nJoin Link: {settings.FRONTEND_URL}/join/{invite_link.code}\n"

        message += """
Log in to the assessment platform to start your exam.

Best regards,
Assessment Engine Team
"""
        result = cls._send_email(subject, message, [student.email])
        if result:
            enrollment.invitation_email_sent = True
            enrollment.save(update_fields=['invitation_email_sent'])
        return result

    @classmethod
    def send_enrollment_confirmation(cls, enrollment):
        """Send enrollment confirmation to student."""
        student = enrollment.student
        exam = enrollment.exam
        
        if not student.email:
            return False

        subject = f"Enrollment Confirmed: {exam.title}"
        message = f"""
Hello {student.get_full_name() or student.username},

Your enrollment has been confirmed for:

Exam: {exam.title}
Course: {exam.course.name}
Duration: {exam.duration_minutes} minutes

You can now access this exam from your dashboard.

Best regards,
Assessment Engine Team
"""
        return cls._send_email(subject, message, [student.email])

    @classmethod
    def send_grade_notification(cls, submission):
        """Send email notification when grades are ready."""
        student = submission.student
        if not student.email:
            return False

        subject = f"Your grades for {submission.exam.title} are ready"
        
        status_text = 'Passed! Congratulations!' if submission.passed else 'Not Passed'
        
        message = f"""
Hello {student.get_full_name() or student.username},

Your submission for "{submission.exam.title}" has been graded.

Results:
- Score: {submission.percentage:.1f}%
- Status: {status_text}
- Attempt: #{submission.attempt_number}

You can view your detailed results by logging into the assessment platform.

Best regards,
Assessment Engine Team
"""
        return cls._send_email(subject, message, [student.email])

    @classmethod
    def send_exam_started_confirmation(cls, submission):
        """Notify student that exam attempt has started."""
        student = submission.student
        if not student.email:
            return False

        exam = submission.exam
        subject = f"Exam Started: {exam.title}"
        message = f"""
Hello {student.get_full_name() or student.username},

You have started the exam: {exam.title}

Details:
- Duration: {exam.duration_minutes} minutes
- Attempt: #{submission.attempt_number}
- Started at: {submission.started_at.strftime('%Y-%m-%d %H:%M')}

Important:
- Complete your exam before the time runs out
- Avoid switching tabs or leaving the exam window
- Submit your answers before closing

Good luck!

Best regards,
Assessment Engine Team
"""
        return cls._send_email(subject, message, [student.email])

    @classmethod
    def send_certificate_notification(cls, submission):
        """Notify student that certificate is available."""
        student = submission.student
        if not student.email or not submission.passed:
            return False

        exam = submission.exam
        subject = f"Certificate Available: {exam.title}"
        message = f"""
Hello {student.get_full_name() or student.username},

Congratulations on passing {exam.title}!

Your completion certificate is now available.

Exam: {exam.title}
Course: {exam.course.name}
Score: {submission.percentage:.1f}%

You can download your certificate from the platform.

Best regards,
Assessment Engine Team
"""
        return cls._send_email(subject, message, [student.email])

    @classmethod
    def send_grade_updated_notification(cls, answer, old_points, new_points):
        """Notify student when their grade is manually adjusted."""
        student = answer.submission.student
        if not student.email:
            return False

        exam = answer.submission.exam
        subject = f"Grade Updated: {exam.title}"
        message = f"""
Hello {student.get_full_name() or student.username},

Your grade for a question in "{exam.title}" has been updated by an educator.

Question: {answer.question.text[:100]}...
Previous Score: {old_points} points
New Score: {new_points} points

Updated Submission Score: {answer.submission.percentage:.1f}%
Status: {'Passed' if answer.submission.passed else 'Not Passed'}

You can view the updated feedback in your submission details.

Best regards,
Assessment Engine Team
"""
        return cls._send_email(subject, message, [student.email])

    # =========================================================================
    # EDUCATOR NOTIFICATIONS
    # =========================================================================

    @classmethod
    def send_submission_notification_to_educator(cls, submission):
        """Notify educator when a student submits an exam."""
        educator = submission.exam.created_by
        if not educator or not educator.email:
            return False

        subject = f"New Submission: {submission.exam.title}"
        message = f"""
Hello {educator.get_full_name() or educator.username},

A student has submitted an exam:

Exam: {submission.exam.title}
Student: {submission.student.get_full_name() or submission.student.username}
Submitted at: {submission.submitted_at.strftime('%Y-%m-%d %H:%M') if submission.submitted_at else 'N/A'}
Score: {submission.percentage:.1f}%
Status: {'Passed' if submission.passed else 'Not Passed'}

{'WARNING: This submission has been flagged for suspicious activity.' if submission.is_suspicious else ''}

View details in your educator dashboard.

Best regards,
Assessment Engine Team
"""
        return cls._send_email(subject, message, [educator.email])

    @classmethod
    def send_flagged_submission_alert(cls, submission):
        """Alert educator about suspicious submission."""
        educator = submission.exam.created_by
        if not educator or not educator.email:
            return False

        subject = f"ALERT: Flagged Submission - {submission.exam.title}"
        message = f"""
Hello {educator.get_full_name() or educator.username},

A submission has been flagged for suspicious activity:

Exam: {submission.exam.title}
Student: {submission.student.get_full_name() or submission.student.username}
Tab Switches: {submission.tab_switch_count}
Focus Lost: {submission.focus_lost_count}
Copy/Paste Attempts: {submission.copy_paste_attempts}
Flags: {', '.join(submission.suspicious_activity_flags) if submission.suspicious_activity_flags else 'None'}

Please review this submission in your educator dashboard.

Best regards,
Assessment Engine Team
"""
        return cls._send_email(subject, message, [educator.email])

    @classmethod
    def send_new_enrollment_notification(cls, enrollment):
        """Notify educator when a student enrolls in their exam."""
        educator = enrollment.exam.created_by
        if not educator or not educator.email:
            return False

        subject = f"New Enrollment: {enrollment.exam.title}"
        message = f"""
Hello {educator.get_full_name() or educator.username},

A new student has enrolled in your exam:

Exam: {enrollment.exam.title}
Student: {enrollment.student.get_full_name() or enrollment.student.username}
Email: {enrollment.student.email}
Enrolled at: {enrollment.enrolled_at.strftime('%Y-%m-%d %H:%M')}

View all enrollments in your educator dashboard.

Best regards,
Assessment Engine Team
"""
        return cls._send_email(subject, message, [educator.email])

    @classmethod
    def send_exam_completion_summary(cls, exam):
        """Send summary to educator when all enrolled students complete exam."""
        educator = exam.created_by
        if not educator or not educator.email:
            return False

        from assessments.models import Submission, ExamEnrollment
        
        total_enrolled = ExamEnrollment.objects.filter(exam=exam, status='enrolled').count()
        submissions = Submission.objects.filter(exam=exam, status__in=['graded', 'flagged'])
        total_submitted = submissions.count()
        passed = submissions.filter(passed=True).count()
        avg_score = submissions.values_list('percentage', flat=True)
        avg = sum(avg_score) / len(avg_score) if avg_score else 0

        subject = f"Exam Summary: {exam.title}"
        message = f"""
Hello {educator.get_full_name() or educator.username},

Here's a summary for your exam: {exam.title}

Statistics:
- Total Enrolled: {total_enrolled}
- Submissions: {total_submitted}
- Passed: {passed} ({(passed/total_submitted*100):.1f}% pass rate)
- Average Score: {avg:.1f}%

View detailed analytics in your educator dashboard.

Best regards,
Assessment Engine Team
"""
        return cls._send_email(subject, message, [educator.email])

    # =========================================================================
    # ADMIN NOTIFICATIONS
    # =========================================================================

    @classmethod
    def send_new_user_notification_to_admin(cls, user, role):
        """Notify admins when a new user registers."""
        from django.contrib.auth.models import User
        from assessments.models import UserProfile
        
        admins = User.objects.filter(
            profile__role='admin',
            is_active=True
        ).values_list('email', flat=True)
        
        admin_emails = [e for e in admins if e]
        if not admin_emails:
            return False

        subject = f"New User Registration: {user.username}"
        message = f"""
Hello Admin,

A new user has registered on the platform:

Username: {user.username}
Email: {user.email}
Role: {role.title()}
Registered at: {user.date_joined.strftime('%Y-%m-%d %H:%M')}

View user details in the admin dashboard.

Best regards,
Assessment Engine Team
"""
        return cls._send_email(subject, message, admin_emails)

    @classmethod
    def send_daily_summary_to_admin(cls, stats):
        """Send daily platform summary to admins."""
        from django.contrib.auth.models import User
        
        admins = User.objects.filter(
            profile__role='admin',
            is_active=True
        ).values_list('email', flat=True)
        
        admin_emails = [e for e in admins if e]
        if not admin_emails:
            return False

        subject = "Daily Platform Summary - Assessment Engine"
        message = f"""
Hello Admin,

Here's your daily platform summary:

Users:
- New registrations: {stats.get('new_users', 0)}
- Total users: {stats.get('total_users', 0)}

Exams:
- New exams created: {stats.get('new_exams', 0)}
- Exams published: {stats.get('published_exams', 0)}

Submissions:
- Total submissions today: {stats.get('submissions_today', 0)}
- Average score: {stats.get('avg_score', 0):.1f}%
- Pass rate: {stats.get('pass_rate', 0):.1f}%

Flagged submissions: {stats.get('flagged_count', 0)}

View detailed analytics in the admin dashboard.

Best regards,
Assessment Engine Team
"""
        return cls._send_email(subject, message, admin_emails)

    # =========================================================================
    # GENERAL NOTIFICATIONS
    # =========================================================================

    @classmethod
    def send_exam_published_notification(cls, exam, students):
        """Notify enrolled students when an exam is published."""
        if not students:
            return 0

        subject = f"Exam Now Available: {exam.title}"
        message = f"""
Hello,

An exam you're enrolled in is now available:

Title: {exam.title}
Course: {exam.course.name}
Duration: {exam.duration_minutes} minutes
Passing Score: {exam.passing_score}%
"""
        if exam.available_from:
            message += f"Available from: {exam.available_from.strftime('%Y-%m-%d %H:%M')}\n"
        if exam.available_until:
            message += f"Available until: {exam.available_until.strftime('%Y-%m-%d %H:%M')}\n"

        message += """
Log in to start your exam.

Best regards,
Assessment Engine Team
"""
        sent = 0
        for student in students:
            if student.email and cls._send_email(subject, message, [student.email]):
                sent += 1
        return sent

    @classmethod
    def send_exam_reminder(cls, exam, students, hours_remaining=24):
        """Send reminder about upcoming exam deadline."""
        if not students:
            return 0

        subject = f"Reminder: {exam.title} - {hours_remaining}h remaining"
        message = f"""
Hello,

This is a reminder that the following exam will close soon:

Title: {exam.title}
Course: {exam.course.name}
Closes: {exam.available_until.strftime('%Y-%m-%d %H:%M') if exam.available_until else 'N/A'}
Time Remaining: {hours_remaining} hours

Don't forget to complete your exam!

Best regards,
Assessment Engine Team
"""
        sent = 0
        for student in students:
            if student.email and cls._send_email(subject, message, [student.email]):
                sent += 1
        return sent

    @classmethod
    def send_welcome_email(cls, user, role):
        """Send welcome email to new users."""
        if not user.email:
            return False

        subject = "Welcome to Assessment Engine"
        message = f"""
Hello {user.get_full_name() or user.username},

Welcome to the Assessment Engine platform!

Your account has been created with the following details:
- Username: {user.username}
- Email: {user.email}
- Role: {role.title()}

"""
        if role == 'student':
            message += "You can now enroll in exams and track your progress.\n"
        elif role == 'educator':
            message += "You can now create courses, exams, and manage your students.\n"
        else:
            message += "You have full administrative access to the platform.\n"

        message += """
Log in to get started!

Best regards,
Assessment Engine Team
"""
        return cls._send_email(subject, message, [user.email])

    @classmethod
    def send_otp_email(cls, user, otp_code, purpose='registration'):
        """Send OTP verification email."""
        if not user.email:
            return False

        if purpose == 'registration':
            subject = "Verify Your Email - Assessment Engine"
            action_text = "complete your registration"
        elif purpose == 'password_reset':
            subject = "Password Reset OTP - Assessment Engine"
            action_text = "reset your password"
        else:
            subject = "Verification Code - Assessment Engine"
            action_text = "verify your action"

        message = f"""
Hello {user.get_full_name() or user.username},

Your verification code to {action_text} is:

    {otp_code}

This code will expire in 10 minutes.

If you didn't request this code, please ignore this email.

Best regards,
Assessment Engine Team
"""
        
        html_message = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
        .otp-code {{ font-size: 32px; font-weight: bold; color: #4F46E5; text-align: center; 
                     padding: 20px; background: white; border-radius: 8px; margin: 20px 0;
                     letter-spacing: 8px; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Assessment Engine</h1>
        </div>
        <div class="content">
            <p>Hello {user.get_full_name() or user.username},</p>
            <p>Your verification code to {action_text} is:</p>
            <div class="otp-code">{otp_code}</div>
            <p><strong>This code will expire in 10 minutes.</strong></p>
            <p>If you didn't request this code, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>Assessment Engine - Built for Acad AI</p>
        </div>
    </div>
</body>
</html>
"""
        return cls._send_email(subject, message, [user.email], html_message=html_message)
