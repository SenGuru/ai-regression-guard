"""
Core AI regression detection logic.
Pure functions and classes - no framework dependencies.
"""
from .scoring import (
    BaseScorer,
    RefusalScorer,
    JsonSchemaScorer,
    CompositeScorer,
    ContainsScorer,
    NotContainsScorer,
    LLMJudgeScorer,
)
from .regressions import detect_regression, should_fail_ci, RegressionResult
from .baselines import BaselineStore, BaselineData, DetailedBaselineData, CaseScore
from .judge_cache import JudgeCache

__all__ = [
    "BaseScorer",
    "RefusalScorer",
    "JsonSchemaScorer",
    "CompositeScorer",
    "ContainsScorer",
    "NotContainsScorer",
    "LLMJudgeScorer",
    "detect_regression",
    "should_fail_ci",
    "RegressionResult",
    "BaselineStore",
    "BaselineData",
    "DetailedBaselineData",
    "CaseScore",
    "JudgeCache",
]
