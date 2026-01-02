"""
Export Service for generating CSV reports.
"""
import csv
import io
from datetime import datetime


class ExportService:
    @staticmethod
    def export_exam_results(exam, submissions):
        """Export exam results to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Student ID', 'Username', 'Email', 'Full Name',
            'Attempt', 'Status', 'Score', 'Percentage', 'Passed',
            'Started At', 'Submitted At', 'Duration (min)',
            'Tab Switches', 'Flagged'
        ])

        for sub in submissions:
            duration = None
            if sub.submitted_at and sub.started_at:
                duration = round((sub.submitted_at - sub.started_at).total_seconds() / 60, 2)

            writer.writerow([
                sub.student.id,
                sub.student.username,
                sub.student.email,
                sub.student.get_full_name(),
                sub.attempt_number,
                sub.status,
                float(sub.score) if sub.score else '',
                float(sub.percentage) if sub.percentage else '',
                'Yes' if sub.passed else 'No' if sub.passed is not None else '',
                sub.started_at.strftime('%Y-%m-%d %H:%M:%S') if sub.started_at else '',
                sub.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if sub.submitted_at else '',
                duration or '',
                sub.tab_switch_count,
                'Yes' if sub.is_suspicious else 'No'
            ])

        return output.getvalue()

    @staticmethod
    def export_detailed_results(exam, submissions):
        """Export detailed results including individual question scores."""
        output = io.StringIO()
        writer = csv.writer(output)

        questions = list(exam.questions.order_by('order'))
        
        # Header
        header = ['Student', 'Email', 'Total Score', 'Percentage', 'Passed']
        for q in questions:
            header.append(f'Q{q.order} ({q.points}pts)')
        writer.writerow(header)

        for sub in submissions:
            row = [
                sub.student.username,
                sub.student.email,
                float(sub.score) if sub.score else 0,
                float(sub.percentage) if sub.percentage else 0,
                'Yes' if sub.passed else 'No'
            ]

            answers = {a.question_id: a for a in sub.answers.all()}
            for q in questions:
                answer = answers.get(q.id)
                if answer:
                    row.append(float(answer.points_earned) if answer.points_earned else 0)
                else:
                    row.append(0)

            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def export_question_analysis(analytics_data):
        """Export question analysis to CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'Question ID', 'Question Text', 'Type', 'Max Points',
            'Attempts', 'Correct', 'Accuracy %',
            'Difficulty Index', 'Difficulty Level',
            'Discrimination Index', 'Discrimination Quality'
        ])

        for q in analytics_data.get('question_analysis', []):
            writer.writerow([
                q['question_id'],
                q['question_text'],
                q['question_type'],
                q['max_points'],
                q['total_attempts'],
                q['correct_count'],
                q['accuracy_rate'],
                q['difficulty_index'],
                q['difficulty_level'],
                q['discrimination_index'],
                q['discrimination_quality']
            ])

        return output.getvalue()

    @staticmethod
    def export_plagiarism_report(plagiarism_data, exam_title):
        """Export plagiarism detection results to CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(['Plagiarism Detection Report'])
        writer.writerow([f'Exam: {exam_title}'])
        writer.writerow([f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
        writer.writerow([])

        if not plagiarism_data.get('flagged_pairs'):
            writer.writerow(['No plagiarism detected'])
            return output.getvalue()

        writer.writerow([
            'Question ID', 'Student 1', 'Submission 1',
            'Student 2', 'Submission 2', 'Similarity %'
        ])

        for pair in plagiarism_data['flagged_pairs']:
            writer.writerow([
                pair['question_id'],
                pair['student_1'],
                pair['submission_1'],
                pair['student_2'],
                pair['submission_2'],
                pair['similarity_percent']
            ])

        return output.getvalue()
