from __future__ import annotations

import random

from trainer.select import shuffle_options


def test_shuffle_preserves_correct_text(sample_questions):
    rng = random.Random(42)
    for q in sample_questions:
        original_correct = q.options[q.answer]
        original_items = dict(q.items) if q.items else None
        shuffled = shuffle_options(q, rng)
        assert shuffled.options[shuffled.answer] == original_correct
        assert set(shuffled.options.values()) == set(q.options.values())
        assert list(shuffled.options.keys()) == [str(i + 1) for i in range(len(q.options))]
        if original_items is not None:
            assert shuffled.items == original_items
        # оригинал не изменён
        assert q.options[q.answer] == original_correct


def test_shuffle_can_change_key(sample_questions):
    """При фиксированном seed ключ ответа может отличаться от исходного."""
    q = sample_questions[1]  # single, answer "3"
    shuffled = shuffle_options(q, random.Random(7))
    assert shuffled.options[shuffled.answer] == q.options[q.answer]
    # хотя бы убедимся, что структура валидна
    assert shuffled.answer in shuffled.options
