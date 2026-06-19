from dataclasses import dataclass
from typing import Literal

Verdict = Literal["pass", "warn", "fail"]


@dataclass
class RuleOutcome:
    verdict: Verdict
    warnings: list[str]


@dataclass
class CadencePattern:
    slug: str
    syllable_template: str
    stress_template: str
    rhyme_compatibility: dict


@dataclass
class ValidationContext:
    cadence_pattern: CadencePattern | None
    emotion: str
    sub_genre: str
