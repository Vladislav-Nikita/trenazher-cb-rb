"""Выбор вопросов по режимам и перемешивание вариантов."""

from __future__ import annotations

import random
from enum import Enum
from typing import Any

from trainer.bank import Question


class Mode(str, Enum):
    TRAINING = "training"
    EXAM = "exam"
    MISTAKES = "mistakes"
    WEAK = "weak"


PASS_THRESHOLD = 0.80
DEFAULT_EXAM_N = 50


def shuffle_options(question: Question, rng: random.Random | None = None) -> Question:
    """
    Перемешивает порядок вариантов; пересчитывает answer.
    items (combo) не трогает. Возвращает копию вопроса.
    """
    rng = rng or random.Random()
    q = question.copy_for_session()
    pairs = list(q.options.items())
    texts = [text for _, text in pairs]
    correct_text = q.options[q.answer]
    rng.shuffle(texts)
    new_options = {str(i + 1): text for i, text in enumerate(texts)}
    new_answer = next(k for k, v in new_options.items() if v == correct_text)
    q.options = new_options
    q.answer = new_answer
    return q


def _progress_entry(progress: dict[str, Any], qid: str) -> dict[str, Any]:
    return (progress.get("questions") or {}).get(qid) or {
        "shown": 0,
        "correct": 0,
        "last_correct": False,
    }


def select_training(
    pool: list[Question],
    n: int,
    rng: random.Random | None = None,
) -> list[Question]:
    rng = rng or random.Random()
    if not pool or n <= 0:
        return []
    k = min(n, len(pool))
    chosen = rng.sample(pool, k)
    return [shuffle_options(q, rng) for q in chosen]


def select_exam(
    pool: list[Question],
    n: int = DEFAULT_EXAM_N,
    rng: random.Random | None = None,
) -> list[Question]:
    return select_training(pool, n, rng)


def select_mistakes(
    pool: list[Question],
    progress: dict[str, Any],
    n: int,
    rng: random.Random | None = None,
) -> list[Question]:
    """
    Вопросы с хотя бы одной ошибкой (shown > 0 и correct < shown),
    по возрастанию точности; затем shuffle options.
    """
    rng = rng or random.Random()
    candidates: list[tuple[float, Question]] = []
    for q in pool:
        entry = _progress_entry(progress, q.id)
        shown = int(entry.get("shown", 0))
        correct = int(entry.get("correct", 0))
        if shown > 0 and correct < shown:
            accuracy = correct / shown
            candidates.append((accuracy, q))
    candidates.sort(key=lambda x: (x[0], x[1].id))
    chosen = [q for _, q in candidates[:n]]
    return [shuffle_options(q, rng) for q in chosen]


def weak_weight(shown: int, correct: int) -> float:
    if shown <= 0:
        return 0.55
    return (shown - correct + 1) / (shown + 2)


def select_weak(
    pool: list[Question],
    progress: dict[str, Any],
    n: int,
    rng: random.Random | None = None,
) -> list[Question]:
    """Взвешенная выборка без возвращения по слабым ответам."""
    rng = rng or random.Random()
    if not pool or n <= 0:
        return []

    remaining = list(pool)
    chosen: list[Question] = []
    k = min(n, len(remaining))

    for _ in range(k):
        weights = []
        for q in remaining:
            entry = _progress_entry(progress, q.id)
            shown = int(entry.get("shown", 0))
            correct = int(entry.get("correct", 0))
            weights.append(weak_weight(shown, correct))
        pick = rng.choices(remaining, weights=weights, k=1)[0]
        chosen.append(pick)
        remaining.remove(pick)

    rng.shuffle(chosen)
    return [shuffle_options(q, rng) for q in chosen]


def select_questions(
    mode: Mode | str,
    pool: list[Question],
    n: int,
    progress: dict[str, Any] | None = None,
    rng: random.Random | None = None,
) -> list[Question]:
    mode = Mode(mode) if not isinstance(mode, Mode) else mode
    progress = progress or {"questions": {}, "exam_attempts": []}
    if mode in (Mode.TRAINING, Mode.EXAM):
        return select_exam(pool, n, rng) if mode == Mode.EXAM else select_training(pool, n, rng)
    if mode == Mode.MISTAKES:
        return select_mistakes(pool, progress, n, rng)
    if mode == Mode.WEAK:
        return select_weak(pool, progress, n, rng)
    raise ValueError(f"Неизвестный режим: {mode}")
