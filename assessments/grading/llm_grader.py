import json
import logging
from typing import Optional
from django.conf import settings
from .base import GradingService, GradingResult

logger = logging.getLogger(__name__)


class LLMGradingService(GradingService):
    """LLM-powered grading with fallback to mock grading."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or settings.GRADING_SERVICE.get('LLM_API_KEY', '')
        self.model = model or settings.GRADING_SERVICE.get('LLM_MODEL', 'gpt-3.5-turbo')
        self._client = None

    def get_service_name(self) -> str:
        return f"llm_{self.model}"

    @property
    def client(self):
        if self._client is None and self.api_key:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("OpenAI package not installed")
            except Exception as e:
                logger.error(f"OpenAI client init failed: {e}")
        return self._client

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
        if question_type in ('mcq', 'tf'):
            return self._grade_objective(selected_choice, expected_answer, max_points, choices)

        if self.client and self.api_key:
            try:
                return self._grade_with_llm(question_type, student_answer, expected_answer, max_points, grading_rubric)
            except Exception as e:
                logger.error(f"LLM grading failed: {e}")

        from .mock_grader import MockGradingService
        result = MockGradingService().grade_answer(
            question_type, student_answer, expected_answer, max_points, choices, selected_choice, grading_rubric
        )
        result.grading_method = f"{self.get_service_name()}_fallback"
        return result

    def _grade_objective(self, selected: Optional[int], expected: str, max_points: float, choices: Optional[list]) -> GradingResult:
        try:
            correct = int(expected)
            is_correct = selected == correct
            return GradingResult(
                max_points if is_correct else 0,
                max_points, is_correct,
                "Correct!" if is_correct else "Incorrect.",
                1.0, self.get_service_name()
            )
        except (ValueError, TypeError):
            return GradingResult(0, max_points, False, "Invalid answer", 1.0, self.get_service_name())

    def _grade_with_llm(self, qtype: str, answer: str, expected: str, max_points: float, rubric: str) -> GradingResult:
        system = """Grade the answer. Respond with JSON only:
{"score_percentage": <0-100>, "is_correct": <bool>, "feedback": "<string>", "confidence": <0.0-1.0>}"""

        user = f"""Type: {qtype}
Max Points: {max_points}
Expected: {expected}
Rubric: {rubric or 'Standard criteria'}
Student Answer: {answer}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.3,
            max_tokens=500
        )

        content = response.choices[0].message.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content)
        score_pct = float(data.get('score_percentage', 0))
        points = round((score_pct / 100) * max_points, 2)

        return GradingResult(
            points, max_points,
            data.get('is_correct', score_pct >= 60),
            data.get('feedback', 'Graded by AI'),
            float(data.get('confidence', 0.8)),
            self.get_service_name()
        )
