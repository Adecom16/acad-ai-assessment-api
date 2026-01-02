"""
Plagiarism Detection Service using TF-IDF and cosine similarity.
Compares student answers against each other to detect potential copying.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from collections import defaultdict


class PlagiarismDetector:
    def __init__(self, similarity_threshold=0.85):
        self.threshold = similarity_threshold
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words='english',
            ngram_range=(1, 3),
            max_features=5000
        )

    def check_exam_submissions(self, submissions):
        """
        Check all submissions for an exam for potential plagiarism.
        Returns list of flagged pairs with similarity scores.
        """
        results = {
            'flagged_pairs': [],
            'submission_scores': {},
            'total_checked': 0,
            'plagiarism_detected': False
        }

        # Group answers by question
        question_answers = defaultdict(list)
        for submission in submissions:
            for answer in submission.answers.all():
                if answer.answer_text and len(answer.answer_text.strip()) > 20:
                    question_answers[answer.question_id].append({
                        'submission_id': submission.id,
                        'student_id': submission.student_id,
                        'student_name': submission.student.username,
                        'answer_text': answer.answer_text,
                        'question_id': answer.question_id
                    })

        # Check each question's answers for similarity
        for question_id, answers in question_answers.items():
            if len(answers) < 2:
                continue

            pairs = self._find_similar_pairs(answers, question_id)
            results['flagged_pairs'].extend(pairs)
            results['total_checked'] += len(answers)

        # Calculate per-submission plagiarism score
        submission_flags = defaultdict(list)
        for pair in results['flagged_pairs']:
            submission_flags[pair['submission_1']].append(pair['similarity'])
            submission_flags[pair['submission_2']].append(pair['similarity'])

        for sub_id, scores in submission_flags.items():
            results['submission_scores'][sub_id] = {
                'max_similarity': round(max(scores) * 100, 2),
                'avg_similarity': round(np.mean(scores) * 100, 2),
                'flag_count': len(scores)
            }

        results['plagiarism_detected'] = len(results['flagged_pairs']) > 0
        return results

    def _find_similar_pairs(self, answers, question_id):
        """Find pairs of answers with similarity above threshold."""
        flagged = []
        
        if len(answers) < 2:
            return flagged

        texts = [a['answer_text'] for a in answers]
        
        try:
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            similarity_matrix = cosine_similarity(tfidf_matrix)

            for i in range(len(answers)):
                for j in range(i + 1, len(answers)):
                    similarity = similarity_matrix[i][j]
                    
                    if similarity >= self.threshold:
                        flagged.append({
                            'question_id': question_id,
                            'submission_1': answers[i]['submission_id'],
                            'student_1': answers[i]['student_name'],
                            'submission_2': answers[j]['submission_id'],
                            'student_2': answers[j]['student_name'],
                            'similarity': round(float(similarity), 4),
                            'similarity_percent': round(float(similarity) * 100, 2)
                        })
        except Exception:
            pass

        return flagged

    def compare_two_texts(self, text1, text2):
        """Compare two specific texts for similarity."""
        if not text1 or not text2:
            return 0.0

        try:
            tfidf_matrix = self.vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return round(float(similarity), 4)
        except Exception:
            return 0.0
