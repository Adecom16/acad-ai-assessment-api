from django.conf import settings
from .base import GradingService
from .mock_grader import MockGradingService
from .llm_grader import LLMGradingService


def get_grading_service(backend: str = None) -> GradingService:
    if backend is None:
        backend = settings.GRADING_SERVICE.get('DEFAULT_BACKEND', 'mock')
    return LLMGradingService() if backend == 'llm' else MockGradingService()
