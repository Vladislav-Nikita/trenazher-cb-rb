from __future__ import annotations

import json
from pathlib import Path

import pytest

from trainer.bank import Question

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_data() -> dict:
    return json.loads((FIXTURES / "sample_bank.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_questions(sample_data) -> list[Question]:
    disc = sample_data["discipline"]
    return [
        Question.from_dict(q, discipline=disc, file_stem="sample")
        for q in sample_data["questions"]
    ]
