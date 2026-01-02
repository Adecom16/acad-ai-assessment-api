from django.db import models


class Answer(models.Model):
    submission = models.ForeignKey(
        'Submission',
        on_delete=models.CASCADE,
        related_name='answers',
        db_index=True
    )
    question = models.ForeignKey(
        'Question',
        on_delete=models.CASCADE,
        related_name='answers',
        db_index=True
    )

    answer_text = models.TextField(blank=True)
    selected_choice = models.IntegerField(null=True, blank=True)

    points_earned = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_correct = models.BooleanField(null=True)
    feedback = models.TextField(blank=True)
    grading_method = models.CharField(max_length=50, blank=True)
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['question__order']
        indexes = [
            models.Index(fields=['submission', 'question']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['submission', 'question'],
                name='unique_submission_question'
            )
        ]

    def __str__(self):
        return f"Answer to Q{self.question.order} by {self.submission.student.username}"
