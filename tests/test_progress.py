from __future__ import annotations

from pathlib import Path

from trainer.progress import (
    empty_progress,
    load_progress,
    record_answer,
    record_exam_attempt,
    reset_progress,
    save_progress,
    stats_by_discipline,
    weak_topics,
)


def test_round_trip(tmp_path: Path, sample_questions):
    path = tmp_path / "progress.json"
    data = empty_progress()
    record_answer(data, "t01-001", False, at="2026-01-01T12:00:00")
    record_answer(data, "t01-001", True, at="2026-01-01T13:00:00")
    record_exam_attempt(
        data,
        n=2,
        correct=1,
        disciplines=["Тестовая дисциплина"],
        at="2026-01-01T14:00:00",
    )
    save_progress(data, path)

    loaded = load_progress(path)
    assert loaded["questions"]["t01-001"]["shown"] == 2
    assert loaded["questions"]["t01-001"]["correct"] == 1
    assert loaded["questions"]["t01-001"]["last_correct"] is True
    assert len(loaded["exam_attempts"]) == 1
    assert loaded["exam_attempts"][0]["pct"] == 50.0
    assert loaded["exam_attempts"][0]["passed"] is False


def test_reset(tmp_path: Path):
    path = tmp_path / "progress.json"
    data = empty_progress()
    record_answer(data, "x", True)
    save_progress(data, path)
    reset_progress(path)
    assert load_progress(path) == empty_progress()


def test_stats_and_weak_topics(sample_questions):
    progress = {
        "version": 1,
        "questions": {
            "t01-001": {"shown": 4, "correct": 1},
            "t01-002": {"shown": 2, "correct": 2},
            "t01-003": {"shown": 2, "correct": 0},
        },
        "exam_attempts": [],
    }
    by_disc = stats_by_discipline(progress, sample_questions)
    assert len(by_disc) == 1
    assert by_disc[0]["shown"] == 8
    assert by_disc[0]["correct"] == 3

    weak = weak_topics(progress, sample_questions, min_shown=2)
    topics = [r["topic"] for r in weak]
    assert "Тема А" in topics
    # Тема А: shown 6, correct 1 → слабее Темы Б (2/2)
    assert weak[0]["topic"] == "Тема А"
