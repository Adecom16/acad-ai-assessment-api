"""
Bulk Import Service for questions via CSV/JSON.
"""
import csv
import json
import io


class BulkImportService:
    REQUIRED_FIELDS = ['question_type', 'text', 'points']
    VALID_TYPES = ['mcq', 'tf', 'short', 'essay']

    @classmethod
    def import_questions_csv(cls, exam, csv_content):
        """
        Import questions from CSV content.
        Expected columns: question_type, text, points, choices (JSON array), expected_answer, grading_rubric
        """
        from assessments.models import Question
        
        results = {'created': 0, 'errors': [], 'questions': []}
        reader = csv.DictReader(io.StringIO(csv_content))
        
        order = exam.questions.count() + 1
        
        for row_num, row in enumerate(reader, start=2):
            try:
                validated = cls._validate_row(row, row_num)
                if validated.get('error'):
                    results['errors'].append(validated['error'])
                    continue

                choices = []
                if row.get('choices'):
                    try:
                        choices = json.loads(row['choices'])
                    except json.JSONDecodeError:
                        choices = [c.strip() for c in row['choices'].split('|')]

                question = Question.objects.create(
                    exam=exam,
                    question_type=row['question_type'].lower(),
                    text=row['text'],
                    points=float(row.get('points', 1)),
                    order=order,
                    choices=choices,
                    expected_answer=row.get('expected_answer', ''),
                    grading_rubric=row.get('grading_rubric', '')
                )
                results['questions'].append({
                    'id': question.id,
                    'text': question.text[:50],
                    'type': question.question_type
                })
                results['created'] += 1
                order += 1

            except Exception as e:
                results['errors'].append(f"Row {row_num}: {str(e)}")

        return results

    @classmethod
    def import_questions_json(cls, exam, json_content):
        """
        Import questions from JSON content.
        Expected format: [{"question_type": "mcq", "text": "...", "points": 2, ...}, ...]
        """
        from assessments.models import Question
        
        results = {'created': 0, 'errors': [], 'questions': []}
        
        try:
            questions_data = json.loads(json_content)
            if not isinstance(questions_data, list):
                questions_data = [questions_data]
        except json.JSONDecodeError as e:
            results['errors'].append(f"Invalid JSON: {str(e)}")
            return results

        order = exam.questions.count() + 1

        for idx, q_data in enumerate(questions_data):
            try:
                validated = cls._validate_row(q_data, idx + 1)
                if validated.get('error'):
                    results['errors'].append(validated['error'])
                    continue

                question = Question.objects.create(
                    exam=exam,
                    question_type=q_data['question_type'].lower(),
                    text=q_data['text'],
                    points=float(q_data.get('points', 1)),
                    order=order,
                    choices=q_data.get('choices', []),
                    expected_answer=q_data.get('expected_answer', ''),
                    grading_rubric=q_data.get('grading_rubric', '')
                )
                results['questions'].append({
                    'id': question.id,
                    'text': question.text[:50],
                    'type': question.question_type
                })
                results['created'] += 1
                order += 1

            except Exception as e:
                results['errors'].append(f"Question {idx + 1}: {str(e)}")

        return results

    @classmethod
    def _validate_row(cls, row, row_num):
        """Validate a question row."""
        for field in cls.REQUIRED_FIELDS:
            if not row.get(field):
                return {'error': f"Row {row_num}: Missing required field '{field}'"}

        q_type = row.get('question_type', '').lower()
        if q_type not in cls.VALID_TYPES:
            return {'error': f"Row {row_num}: Invalid question_type '{q_type}'"}

        if q_type in ['mcq', 'tf'] and not row.get('choices'):
            return {'error': f"Row {row_num}: MCQ/TF questions require choices"}

        return {'valid': True}

    @staticmethod
    def get_csv_template():
        """Return CSV template for question import."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['question_type', 'text', 'points', 'choices', 'expected_answer', 'grading_rubric'])
        writer.writerow(['mcq', 'What is 2+2?', '2', '["3","4","5","6"]', '1', ''])
        writer.writerow(['tf', 'Python is a programming language', '1', '["True","False"]', '0', ''])
        writer.writerow(['short', 'Define polymorphism', '5', '', 'ability of objects to take many forms', 'keywords: objects, forms, inheritance'])
        writer.writerow(['essay', 'Explain OOP principles', '10', '', '', 'Cover: encapsulation, inheritance, polymorphism, abstraction'])
        return output.getvalue()

    @staticmethod
    def get_json_template():
        """Return JSON template for question import."""
        return json.dumps([
            {
                "question_type": "mcq",
                "text": "What is 2+2?",
                "points": 2,
                "choices": ["3", "4", "5", "6"],
                "expected_answer": "1"
            },
            {
                "question_type": "short",
                "text": "Define polymorphism",
                "points": 5,
                "expected_answer": "ability of objects to take many forms",
                "grading_rubric": "keywords: objects, forms, inheritance"
            }
        ], indent=2)
