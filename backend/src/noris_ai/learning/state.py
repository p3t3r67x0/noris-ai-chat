"""Small, deterministic projection of the persisted active conversation branch.

Rebuilding rather than separately updating counters keeps reloads, regeneration,
edits and branch switches consistent. Counts describe activity, never mastery.
"""

from collections.abc import Iterable
from typing import Literal

from pydantic import Field

from noris_ai.core.schemas import ApiSchema


class LearningState(ApiSchema):
    learner_turns: int = Field(default=0, ge=0, le=10_001)
    tutor_turns: int = Field(default=0, ge=0, le=10_001)
    phase: Literal["orientation", "dialogue"] = "orientation"
    review_due: bool = False


def learning_state(turns: Iterable[tuple[str, str]]) -> LearningState:
    """Only nonempty turns from the selected persisted path count as activity."""
    learner_turns = tutor_turns = 0
    for role, content in turns:
        if content.strip():
            learner_turns += role == "user"
            tutor_turns += role == "assistant"
    return LearningState(
        learner_turns=learner_turns,
        tutor_turns=tutor_turns,
        phase="dialogue" if tutor_turns else "orientation",
        review_due=tutor_turns > 0 and tutor_turns % 4 == 0,
    )
