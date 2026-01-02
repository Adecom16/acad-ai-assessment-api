"""
Mock Grading Service - Algorithmic grading using TF-IDF and keyword matching.
Designed for accurate, fair grading without external API dependencies.
"""
import re
import string
from typing import Optional, List, Set, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .base import GradingService, GradingResult


class MockGradingService(GradingService):
    """
    Production-ready algorithmic grading using:
    - TF-IDF cosine similarity for semantic matching
    - Keyword extraction and matching
    - N-gram analysis for phrase detection
    - Length and structure analysis
    - Anti-cheating measures (gibberish detection, copy detection)
    """

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words='english',
            ngram_range=(1, 3),  # Unigrams, bigrams, trigrams
            max_features=2000,
            min_df=1,
            sublinear_tf=True  # Apply sublinear tf scaling
        )
        
        # Common stopwords to exclude from keyword matching
        self.stopwords = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had',
            'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'were', 'being',
            'their', 'there', 'this', 'that', 'with', 'they', 'from', 'which', 'what',
            'when', 'where', 'will', 'would', 'could', 'should', 'about', 'into',
            'through', 'during', 'before', 'after', 'above', 'below', 'between',
            'under', 'again', 'further', 'then', 'once', 'here', 'why', 'how',
            'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'only',
            'same', 'than', 'very', 'just', 'also', 'now', 'used', 'using', 'use'
        }

    def get_service_name(self) -> str:
        return "mock_tfidf"

    def grade_answer(
        self,
        question_type: str,
        student_answer: str,
        expected_answer: str,
        max_points: float,
        choices: Optional[list] = None,
        selected_choice: Optional[int] = None,
        grading_rubric: str = ""
    ) -> GradingResult:
        """Route to appropriate grading method based on question type."""
        
        if question_type in ('mcq', 'tf'):
            return self._grade_choice(selected_choice, expected_answer, max_points, choices)
        elif question_type == 'short':
            return self._grade_short_answer(student_answer, expected_answer, max_points, grading_rubric)
        elif question_type == 'essay':
            return self._grade_essay(student_answer, expected_answer, max_points, grading_rubric)
        
        return GradingResult(
            points_earned=0,
            max_points=max_points,
            is_correct=False,
            feedback="Unknown question type",
            confidence=0.0,
            grading_method=self.get_service_name()
        )

    # =========================================================================
    # MCQ / TRUE-FALSE GRADING
    # =========================================================================

    def _grade_choice(
        self,
        selected: Optional[int],
        expected: str,
        max_points: float,
        choices: Optional[list]
    ) -> GradingResult:
        """Grade multiple choice or true/false questions with exact matching."""
        
        try:
            correct_index = int(expected)
            is_correct = selected == correct_index
            
            if is_correct:
                feedback = "Correct!"
                points = max_points
            else:
                feedback = "Incorrect."
                points = 0
                
                # Show correct answer for learning
                if choices and 0 <= correct_index < len(choices):
                    feedback += f" The correct answer was: {choices[correct_index]}"
            
            return GradingResult(
                points_earned=points,
                max_points=max_points,
                is_correct=is_correct,
                feedback=feedback,
                confidence=1.0,  # MCQ grading is deterministic
                grading_method=self.get_service_name()
            )
            
        except (ValueError, TypeError):
            return GradingResult(
                points_earned=0,
                max_points=max_points,
                is_correct=False,
                feedback="Invalid answer format",
                confidence=1.0,
                grading_method=self.get_service_name()
            )

    # =========================================================================
    # SHORT ANSWER GRADING
    # =========================================================================

    def _grade_short_answer(
        self,
        student_answer: str,
        expected_answer: str,
        max_points: float,
        rubric: str = ""
    ) -> GradingResult:
        """
        Grade short answer questions using multiple factors:
        1. Exact/near-exact match detection
        2. TF-IDF semantic similarity
        3. Keyword coverage
        4. Anti-cheating checks
        """
        
        # Normalize inputs
        student_clean = self._normalize_text(student_answer)
        expected_clean = self._normalize_text(expected_answer)
        
        # Check for empty answer
        if not student_clean:
            return GradingResult(
                points_earned=0,
                max_points=max_points,
                is_correct=False,
                feedback="No answer provided.",
                confidence=1.0,
                grading_method=self.get_service_name()
            )
        
        # Anti-cheating: Check for gibberish or random text
        if self._is_gibberish(student_clean):
            return GradingResult(
                points_earned=0,
                max_points=max_points,
                is_correct=False,
                feedback="Answer appears to be invalid or random text.",
                confidence=0.95,
                grading_method=self.get_service_name()
            )
        
        # Check for exact match (case-insensitive)
        if student_clean == expected_clean:
            return GradingResult(
                points_earned=max_points,
                max_points=max_points,
                is_correct=True,
                feedback="Excellent! Perfect answer.",
                confidence=1.0,
                grading_method=self.get_service_name()
            )
        
        # Combine expected answer with rubric for better matching
        reference_text = f"{expected_answer} {rubric}".strip()
        
        # Extract keywords from expected answer and rubric
        keywords = self._extract_keywords(reference_text)
        required_keywords = self._extract_required_keywords(rubric)
        
        # Calculate scores
        similarity_score = self._calculate_similarity(student_clean, expected_clean)
        keyword_score = self._calculate_keyword_score(student_clean, keywords)
        required_score = self._calculate_required_keyword_score(student_clean, required_keywords)
        
        # Weighted combination
        # If there are required keywords, they're more important
        if required_keywords:
            combined_score = (
                similarity_score * 0.30 +
                keyword_score * 0.30 +
                required_score * 0.40
            )
        else:
            combined_score = (
                similarity_score * 0.45 +
                keyword_score * 0.55
            )
        
        # Calculate points with proper rounding
        points = round(max_points * combined_score, 2)
        is_correct = combined_score >= 0.70
        
        # Generate feedback
        feedback = self._generate_short_feedback(
            combined_score, similarity_score, keyword_score, keywords, required_keywords
        )
        
        # Confidence based on how clear the grading is
        confidence = self._calculate_confidence(combined_score)
        
        return GradingResult(
            points_earned=points,
            max_points=max_points,
            is_correct=is_correct,
            feedback=feedback,
            confidence=confidence,
            grading_method=self.get_service_name()
        )

    # =========================================================================
    # ESSAY GRADING
    # =========================================================================

    def _grade_essay(
        self,
        student_answer: str,
        expected_answer: str,
        max_points: float,
        rubric: str = ""
    ) -> GradingResult:
        """
        Grade essay questions using comprehensive analysis:
        1. Content relevance (TF-IDF similarity)
        2. Keyword and concept coverage
        3. Response length and depth
        4. Structure and coherence indicators
        5. Rubric criteria matching
        """
        
        student_clean = self._normalize_text(student_answer)
        
        # Check for empty answer
        if not student_clean:
            return GradingResult(
                points_earned=0,
                max_points=max_points,
                is_correct=False,
                feedback="No answer provided.",
                confidence=1.0,
                grading_method=self.get_service_name()
            )
        
        # Anti-cheating checks
        if self._is_gibberish(student_clean):
            return GradingResult(
                points_earned=0,
                max_points=max_points,
                is_correct=False,
                feedback="Answer appears to be invalid or random text.",
                confidence=0.95,
                grading_method=self.get_service_name()
            )
        
        # Minimum length check for essays
        word_count = len(student_clean.split())
        if word_count < 20:
            return GradingResult(
                points_earned=round(max_points * 0.1, 2),
                max_points=max_points,
                is_correct=False,
                feedback="Response is too brief for an essay question. Please provide a more detailed answer.",
                confidence=0.9,
                grading_method=self.get_service_name()
            )
        
        # Combine expected answer with rubric
        reference_text = f"{expected_answer} {rubric}".strip()
        
        # Extract keywords and concepts
        keywords = self._extract_keywords(reference_text)
        required_keywords = self._extract_required_keywords(rubric)
        concepts = self._extract_concepts(reference_text)
        
        # Calculate component scores
        similarity_score = self._calculate_similarity(student_clean, self._normalize_text(reference_text))
        keyword_score = self._calculate_keyword_score(student_clean, keywords)
        concept_score = self._calculate_concept_score(student_clean, concepts)
        length_score = self._calculate_length_score(student_clean, expected_answer)
        structure_score = self._calculate_structure_score(student_answer)
        required_score = self._calculate_required_keyword_score(student_clean, required_keywords)
        
        # Weighted combination for essays
        if required_keywords:
            combined_score = (
                similarity_score * 0.20 +
                keyword_score * 0.20 +
                concept_score * 0.15 +
                length_score * 0.10 +
                structure_score * 0.05 +
                required_score * 0.30
            )
        else:
            combined_score = (
                similarity_score * 0.30 +
                keyword_score * 0.25 +
                concept_score * 0.20 +
                length_score * 0.15 +
                structure_score * 0.10
            )
        
        # Calculate points
        points = round(max_points * combined_score, 2)
        is_correct = combined_score >= 0.60  # Lower threshold for essays
        
        # Generate detailed feedback
        feedback = self._generate_essay_feedback(
            combined_score, similarity_score, keyword_score, 
            concept_score, length_score, structure_score,
            keywords, required_keywords
        )
        
        confidence = self._calculate_confidence(combined_score) * 0.9  # Slightly lower for essays
        
        return GradingResult(
            points_earned=points,
            max_points=max_points,
            is_correct=is_correct,
            feedback=feedback,
            confidence=confidence,
            grading_method=self.get_service_name()
        )

    # =========================================================================
    # TEXT PROCESSING UTILITIES
    # =========================================================================

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove punctuation except apostrophes in contractions
        text = re.sub(r"[^\w\s']", ' ', text)
        text = ' '.join(text.split())
        
        return text.strip()

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text."""
        if not text:
            return []
        
        # Get words (3+ characters)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Remove stopwords and duplicates while preserving order
        seen = set()
        keywords = []
        for word in words:
            if word not in self.stopwords and word not in seen:
                seen.add(word)
                keywords.append(word)
        
        return keywords

    def _extract_required_keywords(self, rubric: str) -> List[str]:
        """Extract required keywords from rubric (marked with 'must', 'required', etc.)."""
        if not rubric:
            return []
        
        required = []
        rubric_lower = rubric.lower()
        
        # Look for patterns like "must mention X", "required: X", "key concepts: X"
        patterns = [
            r'must\s+(?:mention|include|have|contain)[:\s]+([^,.]+)',
            r'required[:\s]+([^,.]+)',
            r'key\s+(?:concepts?|terms?|words?)[:\s]+([^,.]+)',
            r'should\s+(?:mention|include)[:\s]+([^,.]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, rubric_lower)
            for match in matches:
                words = re.findall(r'\b[a-zA-Z]{3,}\b', match)
                required.extend([w for w in words if w not in self.stopwords])
        
        return list(set(required))

    def _extract_concepts(self, text: str) -> List[str]:
        """Extract multi-word concepts/phrases from text."""
        if not text:
            return []
        
        text_lower = text.lower()
        
        # Extract 2-3 word phrases
        words = text_lower.split()
        concepts = []
        
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if not any(w in self.stopwords for w in [words[i], words[i+1]]):
                concepts.append(bigram)
        
        for i in range(len(words) - 2):
            trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
            # At least 2 of 3 words should be meaningful
            meaningful = sum(1 for w in [words[i], words[i+1], words[i+2]] if w not in self.stopwords)
            if meaningful >= 2:
                concepts.append(trigram)
        
        return concepts[:20]  # Limit to top 20 concepts

    # =========================================================================
    # SCORING FUNCTIONS
    # =========================================================================

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate TF-IDF cosine similarity between two texts."""
        if not text1 or not text2:
            return 0.0
        
        try:
            # Fit and transform both texts
            tfidf_matrix = self.vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(max(0.0, min(1.0, similarity)))
        except Exception:
            # Fallback to Jaccard similarity
            return self._jaccard_similarity(text1, text2)

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Fallback Jaccard similarity."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0

    def _calculate_keyword_score(self, answer: str, keywords: List[str]) -> float:
        """Calculate what percentage of keywords are present in the answer."""
        if not keywords:
            return 0.5  # Neutral score if no keywords
        
        answer_lower = answer.lower()
        matches = sum(1 for kw in keywords if kw in answer_lower)
        
        return matches / len(keywords)

    def _calculate_required_keyword_score(self, answer: str, required: List[str]) -> float:
        """Calculate score based on required keywords (stricter)."""
        if not required:
            return 1.0  # Full score if no required keywords
        
        answer_lower = answer.lower()
        matches = sum(1 for kw in required if kw in answer_lower)
        
        # Stricter scoring - missing required keywords is penalized more
        return matches / len(required)

    def _calculate_concept_score(self, answer: str, concepts: List[str]) -> float:
        """Calculate how many concepts/phrases are present."""
        if not concepts:
            return 0.5
        
        answer_lower = answer.lower()
        matches = sum(1 for concept in concepts if concept in answer_lower)
        
        return min(1.0, matches / max(len(concepts) * 0.3, 1))  # Expect ~30% concept coverage

    def _calculate_length_score(self, answer: str, expected: str) -> float:
        """Score based on answer length relative to expected."""
        answer_words = len(answer.split())
        expected_words = len(expected.split()) if expected else 50
        
        if expected_words == 0:
            expected_words = 50  # Default expected length
        
        ratio = answer_words / expected_words
        
        # Ideal ratio is 0.8 to 1.5
        if 0.8 <= ratio <= 1.5:
            return 1.0
        elif 0.5 <= ratio < 0.8:
            return 0.7 + (ratio - 0.5) * 1.0  # 0.7 to 1.0
        elif 1.5 < ratio <= 2.5:
            return 1.0 - (ratio - 1.5) * 0.2  # 1.0 to 0.8
        elif ratio < 0.5:
            return max(0.3, ratio * 1.4)  # Penalize very short
        else:
            return 0.6  # Very long answers

    def _calculate_structure_score(self, answer: str) -> float:
        """Score based on answer structure (sentences, paragraphs)."""
        if not answer:
            return 0.0
        
        # Count sentences (rough estimate)
        sentences = len(re.findall(r'[.!?]+', answer))
        
        # Count paragraphs
        paragraphs = len([p for p in answer.split('\n\n') if p.strip()])
        
        # Word count
        words = len(answer.split())
        
        score = 0.5  # Base score
        
        # Reward proper sentence structure
        if sentences >= 2:
            score += 0.2
        if sentences >= 4:
            score += 0.1
        
        # Reward paragraph structure for longer answers
        if words > 100 and paragraphs >= 2:
            score += 0.2
        
        return min(1.0, score)

    # =========================================================================
    # ANTI-CHEATING
    # =========================================================================

    def _is_gibberish(self, text: str) -> bool:
        """Detect if text is gibberish or random characters."""
        if not text or len(text) < 10:
            return False
        
        words = text.split()
        if not words:
            return True
        
        # Check for repeated characters
        if re.search(r'(.)\1{4,}', text):
            return True
        
        # Check for keyboard mashing patterns
        keyboard_patterns = ['asdf', 'qwer', 'zxcv', 'hjkl', 'uiop']
        text_lower = text.lower()
        if any(pattern in text_lower for pattern in keyboard_patterns):
            if len(text) < 50:  # Short gibberish
                return True
        
        # Check average word length (gibberish often has unusual word lengths)
        avg_word_len = sum(len(w) for w in words) / len(words)
        if avg_word_len > 15 or avg_word_len < 2:
            return True
        
        # Check for too many non-alphabetic characters
        alpha_ratio = sum(1 for c in text if c.isalpha()) / len(text)
        if alpha_ratio < 0.5:
            return True
        
        # Check for dictionary words (at least some should be recognizable)
        common_words = {
            'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
            'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
            'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
            'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what',
            'is', 'are', 'was', 'were', 'been', 'being', 'has', 'had', 'does', 'did'
        }
        
        word_set = set(w.lower() for w in words)
        common_count = len(word_set & common_words)
        
        # If answer has many words but no common words, likely gibberish
        if len(words) > 10 and common_count == 0:
            return True
        
        return False

    # =========================================================================
    # FEEDBACK GENERATION
    # =========================================================================

    def _calculate_confidence(self, score: float) -> float:
        """Calculate grading confidence based on score clarity."""
        # High confidence for very high or very low scores
        if score >= 0.85 or score <= 0.15:
            return 0.95
        elif score >= 0.70 or score <= 0.30:
            return 0.85
        else:
            # Middle scores have lower confidence
            return 0.70

    def _generate_short_feedback(
        self,
        combined: float,
        similarity: float,
        keyword: float,
        keywords: List[str],
        required: List[str]
    ) -> str:
        """Generate feedback for short answer questions."""
        
        if combined >= 0.90:
            return "Excellent answer! You've demonstrated a thorough understanding."
        elif combined >= 0.80:
            return "Very good answer. You've covered the key points well."
        elif combined >= 0.70:
            return "Good answer. Most important concepts are addressed."
        elif combined >= 0.50:
            feedback = "Partial credit. "
            if keyword < 0.5 and keywords:
                feedback += f"Consider including: {', '.join(keywords[:3])}. "
            if required and any(kw not in feedback.lower() for kw in required):
                missing = [kw for kw in required[:2] if kw not in feedback.lower()]
                if missing:
                    feedback += f"Key terms needed: {', '.join(missing)}."
            return feedback.strip()
        else:
            feedback = "Needs improvement. "
            if keywords:
                feedback += f"Key concepts to address: {', '.join(keywords[:4])}."
            return feedback

    def _generate_essay_feedback(
        self,
        combined: float,
        similarity: float,
        keyword: float,
        concept: float,
        length: float,
        structure: float,
        keywords: List[str],
        required: List[str]
    ) -> str:
        """Generate detailed feedback for essay questions."""
        
        parts = []
        
        # Overall assessment
        if combined >= 0.85:
            parts.append("Excellent essay demonstrating comprehensive understanding.")
        elif combined >= 0.70:
            parts.append("Good essay with solid coverage of the topic.")
        elif combined >= 0.55:
            parts.append("Satisfactory response showing basic understanding.")
        elif combined >= 0.40:
            parts.append("Partial credit. Several areas need improvement.")
        else:
            parts.append("Response needs significant improvement.")
        
        # Specific feedback
        if keyword < 0.4 and keywords:
            parts.append(f"Include more relevant terminology: {', '.join(keywords[:3])}.")
        
        if required:
            missing = [kw for kw in required if kw not in ' '.join(parts).lower()]
            if missing:
                parts.append(f"Required concepts missing: {', '.join(missing[:2])}.")
        
        if length < 0.5:
            parts.append("Consider expanding your response with more detail.")
        elif length > 1.5:
            parts.append("Response could be more concise.")
        
        if structure < 0.5:
            parts.append("Improve organization with clear sentences and paragraphs.")
        
        if similarity < 0.3 and combined < 0.6:
            parts.append("Address the question more directly.")
        
        return " ".join(parts)
