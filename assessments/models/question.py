from django.db import models
from django.core.validators import MinValueValidator


class Question(models.Model):
    class QuestionType(models.TextChoices):
        MULTIPLE_CHOICE = 'mcq', 'Multiple Choice'
        TRUE_FALSE = 'tf', 'True/False'
        SHORT_ANSWER = 'short', 'Short Answer'
        ESSAY = 'essay', 'Essay'

    exam = models.ForeignKey(
        'Exam',
        on_delete=models.CASCADE,
        related_name='questions',
        db_index=True
    )
    question_type = models.CharField(
        max_length=10,
        choices=QuestionType.choices,
        db_index=True
    )
    text = models.TextField()
    points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.00,
        validators=[MinValueValidator(0)]
    )
    order = models.PositiveIntegerField(default=0)
    choices = models.JSONField(null=True, blank=True)
    expected_answer = models.TextField()
    grading_rubric = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['exam', 'order']),
        ]

    def __str__(self):
        return f"Q{self.order}: {self.text[:50]}..."
