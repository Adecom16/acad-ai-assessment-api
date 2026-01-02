from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class GradingResult:
    points_earned: float
    max_points: float
    is_correct: bool
    feedback: str
    confidence: float
    grading_method: str

    @property
    def percentage(self) -> float:
        if self.max_points == 0:
            return 0.0
        return (self.points_earned / self.max_points) * 100


class GradingService(ABC):
    @abstractmethod
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
        pass

    @abstractmethod
    def get_service_name(self) -> str:
        pass
