"""
Leaderboard Service for exam rankings and student performance tracking.
Demonstrates advanced query optimization with annotations and aggregations.
"""
from django.db.models import Avg, Count, Max, Min, F, Window, Sum
from django.db.models.functions import Rank, DenseRank, PercentRank
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from assessments.models import Submission, Exam


class LeaderboardService:
    """
    Service for generating leaderboards and performance rankings.
    Uses optimized queries with window functions for efficient ranking.
    """
    
    @classmethod
    def get_exam_leaderboard(cls, exam_id: int, limit: int = 50) -> dict:
        """
        Get leaderboard for a specific exam.
        Uses window functions for efficient ranking.
        """
        submissions = Submission.objects.filter(
            exam_id=exam_id,
            status=Submission.Status.GRADED
        ).select_related('student').annotate(
            rank=Window(
                expression=DenseRank(),
                order_by=F('percentage').desc()
            ),
            percentile=Window(
                expression=PercentRank(),
                order_by=F('percentage').asc()
            )
        ).order_by('rank', '-submitted_at')[:limit]
        
        leaderboard = []
        for sub in submissions:
            leaderboard.append({
                'rank': sub.rank,
                'student_id': sub.student.id,
                'student_name': sub.student.get_full_name() or sub.student.username,
                'score': float(sub.score) if sub.score else 0,
                'percentage': float(sub.percentage) if sub.percentage else 0,
                'percentile': round((1 - sub.percentile) * 100, 1),
                'attempt_number': sub.attempt_number,
                'submitted_at': sub.submitted_at,
                'passed': sub.passed
            })
        
        # Get exam stats
        stats = Submission.objects.filter(
            exam_id=exam_id,
            status=Submission.Status.GRADED
        ).aggregate(
            total_submissions=Count('id'),
            avg_score=Avg('percentage'),
            max_score=Max('percentage'),
            min_score=Min('percentage'),
            pass_count=Count('id', filter=F('passed'))
        )
        
        return {
            'exam_id': exam_id,
            'leaderboard': leaderboard,
            'statistics': {
                'total_submissions': stats['total_submissions'] or 0,
                'average_score': round(stats['avg_score'] or 0, 2),
                'highest_score': round(stats['max_score'] or 0, 2),
                'lowest_score': round(stats['min_score'] or 0, 2),
                'pass_rate': round((stats['pass_count'] / stats['total_submissions'] * 100) if stats['total_submissions'] else 0, 2)
            }
        }
    
    @classmethod
    def get_student_ranking(cls, student_id: int, exam_id: int) -> dict:
        """Get a specific student's ranking in an exam."""
        try:
            submission = Submission.objects.filter(
                student_id=student_id,
                exam_id=exam_id,
                status=Submission.Status.GRADED
            ).order_by('-percentage').first()
            
            if not submission:
                return {'error': 'No graded submission found'}
            
            # Count students with higher scores
            higher_count = Submission.objects.filter(
                exam_id=exam_id,
                status=Submission.Status.GRADED,
                percentage__gt=submission.percentage
            ).values('student').distinct().count()
            
            total_students = Submission.objects.filter(
                exam_id=exam_id,
                status=Submission.Status.GRADED
            ).values('student').distinct().count()
            
            rank = higher_count + 1
            percentile = ((total_students - rank) / total_students * 100) if total_students > 0 else 0
            
            return {
                'student_id': student_id,
                'exam_id': exam_id,
                'rank': rank,
                'total_students': total_students,
                'percentile': round(percentile, 1),
                'score': float(submission.percentage),
                'passed': submission.passed
            }
        except Exception as e:
            return {'error': str(e)}
    
    @classmethod
    def get_course_leaderboard(cls, course_id: int, limit: int = 20) -> dict:
        """
        Get overall leaderboard for a course across all exams.
        Aggregates student performance across multiple exams.
        """
        # Get students with their average performance in the course
        student_stats = Submission.objects.filter(
            exam__course_id=course_id,
            status=Submission.Status.GRADED
        ).values('student', 'student__username', 'student__first_name', 'student__last_name').annotate(
            avg_score=Avg('percentage'),
            total_exams=Count('exam', distinct=True),
            total_submissions=Count('id'),
            total_passed=Count('id', filter=F('passed'))
        ).order_by('-avg_score')[:limit]
        
        leaderboard = []
        for idx, stat in enumerate(student_stats, 1):
            name = f"{stat['student__first_name']} {stat['student__last_name']}".strip()
            leaderboard.append({
                'rank': idx,
                'student_id': stat['student'],
                'student_name': name or stat['student__username'],
                'average_score': round(stat['avg_score'] or 0, 2),
                'exams_taken': stat['total_exams'],
                'total_submissions': stat['total_submissions'],
                'pass_rate': round((stat['total_passed'] / stat['total_submissions'] * 100) if stat['total_submissions'] else 0, 1)
            })
        
        return {
            'course_id': course_id,
            'leaderboard': leaderboard
        }
    
    @classmethod
    def get_trending_performers(cls, days: int = 7, limit: int = 10) -> dict:
        """
        Get students with the most improvement in recent days.
        Compares recent performance to historical average.
        """
        cutoff = timezone.now() - timedelta(days=days)
        
        # Get recent high performers
        recent_performers = Submission.objects.filter(
            status=Submission.Status.GRADED,
            submitted_at__gte=cutoff
        ).values('student', 'student__username').annotate(
            recent_avg=Avg('percentage'),
            recent_count=Count('id')
        ).filter(recent_count__gte=2).order_by('-recent_avg')[:limit]
        
        trending = []
        for perf in recent_performers:
            # Get historical average (before the cutoff)
            historical = Submission.objects.filter(
                student_id=perf['student'],
                status=Submission.Status.GRADED,
                submitted_at__lt=cutoff
            ).aggregate(avg=Avg('percentage'))
            
            historical_avg = historical['avg'] or perf['recent_avg']
            improvement = perf['recent_avg'] - historical_avg
            
            trending.append({
                'student_id': perf['student'],
                'student_name': perf['student__username'],
                'recent_average': round(perf['recent_avg'], 2),
                'historical_average': round(historical_avg, 2),
                'improvement': round(improvement, 2),
                'recent_submissions': perf['recent_count']
            })
        
        # Sort by improvement
        trending.sort(key=lambda x: x['improvement'], reverse=True)
        
        return {
            'period_days': days,
            'trending_performers': trending
        }
