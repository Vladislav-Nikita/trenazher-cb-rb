from __future__ import annotations

import random

from trainer.select import (
    Mode,
    select_mistakes,
    select_questions,
    select_training,
    select_weak,
    weak_weight,
)


def test_select_training_size_and_no_dupes(sample_questions):
    rng = random.Random(1)
    chosen = select_training(sample_questions, n=3, rng=rng)
    assert len(chosen) == 3
    assert len({q.id for q in chosen}) == 3


def test_select_training_caps_at_pool(sample_questions):
    chosen = select_training(sample_questions, n=100, rng=random.Random(0))
    assert len(chosen) == len(sample_questions)


def test_select_mistakes_only_wrong(sample_questions):
    progress = {
        "questions": {
            "t01-001": {"shown": 2, "correct": 1},  # была ошибка
            "t01-002": {"shown": 3, "correct": 3},  # всё верно — нет
            "t01-003": {"shown": 1, "correct": 0},  # ошибка
            "t01-004": {"shown": 0, "correct": 0},  # не видели
        },
        "exam_attempts": [],
    }
    chosen = select_mistakes(sample_questions, progress, n=10, rng=random.Random(0))
    ids = [q.id for q in chosen]
    assert ids == ["t01-003", "t01-001"]  # точность 0.0 затем 0.5


def test_select_mistakes_empty(sample_questions):
    progress = {"questions": {}, "exam_attempts": []}
    assert select_mistakes(sample_questions, progress, n=5) == []


def test_weak_weight_unseen_and_seen():
    assert weak_weight(0, 0) == 0.55
    assert weak_weight(4, 1) == (4 - 1 + 1) / (4 + 2)


def test_select_weak_prefers_weak(sample_questions):
    progress = {
        "questions": {
            "t01-001": {"shown": 10, "correct": 0},
            "t01-002": {"shown": 10, "correct": 10},
            "t01-003": {"shown": 10, "correct": 10},
            "t01-004": {"shown": 10, "correct": 10},
            "t01-005": {"shown": 10, "correct": 10},
        },
        "exam_attempts": [],
    }
    # при сильном перекосе весов слабый почти всегда первый в серии выборок
    hits = 0
    for seed in range(30):
        chosen = select_weak(sample_questions, progress, n=1, rng=random.Random(seed))
        if chosen and chosen[0].id == "t01-001":
            hits += 1
    assert hits >= 20


def test_select_questions_modes(sample_questions):
    progress = {
        "questions": {"t01-001": {"shown": 2, "correct": 0}},
        "exam_attempts": [],
    }
    assert len(select_questions(Mode.TRAINING, sample_questions, 2, progress, random.Random(0))) == 2
    assert len(select_questions("exam", sample_questions, 2, progress, random.Random(0))) == 2
    mistakes = select_questions(Mode.MISTAKES, sample_questions, 5, progress, random.Random(0))
    assert [q.id for q in mistakes] == ["t01-001"]
