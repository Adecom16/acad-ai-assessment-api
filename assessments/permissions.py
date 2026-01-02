from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or _is_admin(request.user):
            return True
        if hasattr(obj, 'student'):
            return obj.student == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False


class IsEducatorOrAdmin(permissions.BasePermission):
    message = "Only educators and admins can perform this action."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return _is_educator(request.user) or _is_admin(request.user) or request.user.is_staff


class IsAdminUser(permissions.BasePermission):
    message = "Only admins can perform this action."

    def has_permission(self, request, view):
        return _is_admin(request.user) or request.user.is_staff


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff or _is_educator(request.user) or _is_admin(request.user)


class CanSubmitExam(permissions.BasePermission):
    message = "You cannot submit to this exam."

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or _is_admin(request.user):
            return True
        if obj.student != request.user:
            return False
        if obj.status != 'in_progress':
            self.message = "This submission is no longer in progress."
            return False
        if obj.is_expired:
            self.message = "This submission has expired."
            return False
        return True


def _is_educator(user):
    return hasattr(user, 'profile') and user.profile.role == 'educator'


def _is_admin(user):
    return hasattr(user, 'profile') and user.profile.role == 'admin'


def _is_student(user):
    return hasattr(user, 'profile') and user.profile.role == 'student'
