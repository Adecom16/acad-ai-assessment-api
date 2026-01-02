"""
Exam Analytics Service.
Provides detailed statistics and insights for exams and questions.
"""
from django.db.models import Avg, Count, StdDev, F, Q, Case, When, FloatField
from collections import defaultdict
import numpy as np


class ExamAnalytics:
    def __init__(self, exam):
        self.exam = exam

    def get_full_analytics(self):
        """Get comprehensive analytics for the exam."""
        return {
            'exam_info': self._get_exam_info(),
            'overall_stats': self._get_overall_stats(),
            'question_analysis': self._get_question_analysis(),
            'score_distribution': self._get_score_distribution(),
            'time_analysis': self._get_time_analysis(),
            'pass_fail_breakdown': self._get_pass_fail_breakdown(),
        }

    def _get_exam_info(self):
        return {
            'id': self.exam.id,
            'title': self.exam.title,
            'course': self.exam.course.name,
            'total_points': float(self.exam.get_total_points()),
            'question_count': self.exam.get_question_count(),
            'passing_score': float(self.exam.passing_score),
            'duration_minutes': self.exam.duration_minutes
        }

    def _get_overall_stats(self):
        from assessments.models import Submission
        
        submissions = Submission.objects.filter(
            exam=self.exam,
            status=Submission.Status.GRADED
        )

        if not submissions.exists():
            return {'message': 'No graded submissions yet'}

        # Get basic stats first
        stats = submissions.aggregate(
            total=Count('id'),
            avg_score=Avg('percentage'),
            std_dev=StdDev('percentage'),
            avg_points=Avg('score')
        )
        
        # Calculate pass/fail counts manually since 'passed' is a property
        passing_score = float(self.exam.passing_score)
        pass_count = submissions.filter(percentage__gte=passing_score).count()
        fail_count = submissions.filter(percentage__lt=passing_score).count()

        scores = list(submissions.values_list('percentage', flat=True))
        
        return {
            'total_submissions': stats['total'],
            'average_score': round(stats['avg_score'] or 0, 2),
            'std_deviation': round(stats['std_dev'] or 0, 2),
            'median_score': round(float(np.median(scores)), 2) if scores else 0,
            'highest_score': round(max(scores), 2) if scores else 0,
            'lowest_score': round(min(scores), 2) if scores else 0,
            'pass_count': pass_count,
            'fail_count': fail_count,
            'pass_rate': round((pass_count / stats['total']) * 100, 2) if stats['total'] > 0 else 0
        }

    def _get_question_analysis(self):
        """Analyze each question's performance metrics."""
        from assessments.models import Answer, Submission
        
        questions = self.exam.questions.all()
        analysis = []

        for question in questions:
            answers = Answer.objects.filter(
                question=question,
                submission__status=Submission.Status.GRADED
            )

            if not answers.exists():
                continue

            total = answers.count()
            correct = answers.filter(is_correct=True).count()
            
            points_data = answers.aggregate(
                avg_points=Avg('points_earned'),
                total_attempts=Count('id')
            )

            # Calculate difficulty index (proportion correct)
            difficulty = correct / total if total > 0 else 0
            
            # Calculate discrimination index
            discrimination = self._calculate_discrimination(question)

            # For MCQ, get choice distribution
            choice_distribution = None
            if question.question_type in ['mcq', 'tf'] and question.choices:
                choice_distribution = self._get_choice_distribution(answers, question.choices)

            analysis.append({
                'question_id': question.id,
                'question_text': question.text[:100] + '...' if len(question.text) > 100 else question.text,
                'question_type': question.question_type,
                'max_points': float(question.points),
                'total_attempts': total,
                'correct_count': correct,
                'incorrect_count': total - correct,
                'accuracy_rate': round((correct / total) * 100, 2) if total > 0 else 0,
                'average_points': round(points_data['avg_points'] or 0, 2),
                'difficulty_index': round(difficulty, 3),
                'difficulty_level': self._get_difficulty_level(difficulty),
                'discrimination_index': round(discrimination, 3),
                'discrimination_quality': self._get_discrimination_quality(discrimination),
                'choice_distribution': choice_distribution
            })

        return sorted(analysis, key=lambda x: x['difficulty_index'])

    def _calculate_discrimination(self, question):
        """
        Calculate discrimination index using point-biserial correlation.
        Measures how well the question differentiates between high and low performers.
        """
        from assessments.models import Answer, Submission
        
        submissions = Submission.objects.filter(
            exam=self.exam,
            status=Submission.Status.GRADED
        ).order_by('-percentage')

        if submissions.count() < 4:
            return 0

        # Split into top 27% and bottom 27%
        n = submissions.count()
        top_n = max(1, int(n * 0.27))
        
        top_submissions = submissions[:top_n]
        bottom_submissions = submissions[n - top_n:]

        top_correct = Answer.objects.filter(
            question=question,
            submission__in=top_submissions,
            is_correct=True
        ).count()

        bottom_correct = Answer.objects.filter(
            question=question,
            submission__in=bottom_submissions,
            is_correct=True
        ).count()

        # Discrimination = (top correct - bottom correct) / n
        discrimination = (top_correct - bottom_correct) / top_n if top_n > 0 else 0
        return max(-1, min(1, discrimination))

    def _get_difficulty_level(self, index):
        if index >= 0.8:
            return 'Very Easy'
        elif index >= 0.6:
            return 'Easy'
        elif index >= 0.4:
            return 'Moderate'
        elif index >= 0.2:
            return 'Difficult'
        else:
            return 'Very Difficult'

    def _get_discrimination_quality(self, index):
        if index >= 0.4:
            return 'Excellent'
        elif index >= 0.3:
            return 'Good'
        elif index >= 0.2:
            return 'Acceptable'
        elif index >= 0.1:
            return 'Poor'
        else:
            return 'Very Poor - Consider revising'

    def _get_choice_distribution(self, answers, choices):
        distribution = {i: 0 for i in range(len(choices))}
        
        for answer in answers:
            if answer.selected_choice is not None and 0 <= answer.selected_choice < len(choices):
                distribution[answer.selected_choice] += 1

        total = sum(distribution.values())
        return [
            {
                'choice_index': i,
                'choice_text': choices[i] if i < len(choices) else '',
                'count': count,
                'percentage': round((count / total) * 100, 2) if total > 0 else 0
            }
            for i, count in distribution.items()
        ]

    def _get_score_distribution(self):
        """Get score distribution in ranges."""
        from assessments.models import Submission
        
        submissions = Submission.objects.filter(
            exam=self.exam,
            status=Submission.Status.GRADED
        )

        ranges = [
            (0, 10), (10, 20), (20, 30), (30, 40), (40, 50),
            (50, 60), (60, 70), (70, 80), (80, 90), (90, 100)
        ]

        distribution = []
        for low, high in ranges:
            count = submissions.filter(
                percentage__gte=low,
                percentage__lt=high if high < 100 else 101
            ).count()
            distribution.append({
                'range': f'{low}-{high}%',
                'count': count
            })

        return distribution

    def _get_time_analysis(self):
        """Analyze submission timing patterns."""
        from assessments.models import Submission
        
        submissions = Submission.objects.filter(
            exam=self.exam,
            status=Submission.Status.GRADED,
            submitted_at__isnull=False
        )

        if not submissions.exists():
            return {'message': 'No timing data available'}

        durations = []
        for sub in submissions:
            if sub.submitted_at and sub.started_at:
                duration = (sub.submitted_at - sub.started_at).total_seconds() / 60
                durations.append(duration)

        if not durations:
            return {'message': 'No timing data available'}

        return {
            'average_duration_minutes': round(np.mean(durations), 2),
            'median_duration_minutes': round(np.median(durations), 2),
            'fastest_completion': round(min(durations), 2),
            'slowest_completion': round(max(durations), 2),
            'allowed_duration': self.exam.duration_minutes
        }

    def _get_pass_fail_breakdown(self):
        """Get detailed pass/fail analysis."""
        from assessments.models import Submission
        
        submissions = Submission.objects.filter(
            exam=self.exam,
            status=Submission.Status.GRADED
        )

        passing_score = float(self.exam.passing_score)
        passed = submissions.filter(percentage__gte=passing_score)
        failed = submissions.filter(percentage__lt=passing_score)

        return {
            'passing_threshold': float(self.exam.passing_score),
            'passed': {
                'count': passed.count(),
                'average_score': round(passed.aggregate(avg=Avg('percentage'))['avg'] or 0, 2)
            },
            'failed': {
                'count': failed.count(),
                'average_score': round(failed.aggregate(avg=Avg('percentage'))['avg'] or 0, 2)
            }
        }
