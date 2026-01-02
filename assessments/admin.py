from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Course, Exam, Question, Submission, Answer, AuditLog, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'


class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'profile__role']

    def get_role(self, obj):
        return obj.profile.get_role_display() if hasattr(obj, 'profile') else '-'
    get_role.short_description = 'Role'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ['order', 'question_type', 'text', 'points', 'expected_answer']


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ['question', 'answer_text', 'selected_choice', 'points_earned', 'is_correct', 'feedback']
    can_delete = False


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'created_at']
    search_fields = ['code', 'name']
    ordering = ['code']


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'status', 'duration_minutes', 'passing_score', 'browser_lockdown', 'created_at']
    list_filter = ['status', 'course', 'browser_lockdown']
    search_fields = ['title', 'description']
    inlines = [QuestionInline]
    readonly_fields = ['created_at', 'updated_at', 'published_at']
    fieldsets = (
        (None, {'fields': ('title', 'description', 'course', 'status')}),
        ('Settings', {'fields': ('duration_minutes', 'passing_score', 'max_attempts', 'shuffle_questions', 'show_results_immediately')}),
        ('Anti-Cheating', {'fields': ('browser_lockdown', 'allow_copy_paste', 'webcam_required', 'max_tab_switches')}),
        ('Metadata', {'fields': ('created_by', 'created_at', 'updated_at', 'published_at'), 'classes': ('collapse',)}),
    )


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'exam', 'question_type', 'text_preview', 'points', 'order']
    list_filter = ['question_type', 'exam']
    search_fields = ['text']

    def text_preview(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Question'


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'exam', 'status', 'score', 'percentage', 'passed', 'is_suspicious_display', 'submitted_at']
    list_filter = ['status', 'passed', 'exam']
    search_fields = ['student__username', 'exam__title']
    inlines = [AnswerInline]
    readonly_fields = ['started_at', 'submitted_at', 'graded_at', 'ip_address', 'user_agent', 'browser_fingerprint']
    fieldsets = (
        (None, {'fields': ('student', 'exam', 'status', 'attempt_number')}),
        ('Results', {'fields': ('score', 'percentage', 'passed')}),
        ('Anti-Cheating Metrics', {'fields': ('tab_switch_count', 'focus_lost_count', 'copy_paste_attempts', 'suspicious_activity_flags')}),
        ('Security Info', {'fields': ('ip_address', 'user_agent', 'browser_fingerprint'), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('started_at', 'submitted_at', 'graded_at'), 'classes': ('collapse',)}),
    )

    def is_suspicious_display(self, obj):
        return obj.is_suspicious
    is_suspicious_display.boolean = True
    is_suspicious_display.short_description = 'Suspicious'


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['id', 'submission', 'question', 'is_correct', 'points_earned']
    list_filter = ['is_correct', 'grading_method']
    readonly_fields = ['answered_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'event_type', 'user', 'ip_address', 'description_preview']
    list_filter = ['event_type', 'created_at']
    search_fields = ['user__username', 'description', 'ip_address']
    readonly_fields = ['user', 'event_type', 'description', 'ip_address', 'user_agent', 'metadata', 'created_at']
    ordering = ['-created_at']

    def description_preview(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_preview.short_description = 'Description'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
