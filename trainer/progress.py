"""Локальный прогресс в data/progress.json."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trainer.bank import Question

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROGRESS_PATH = ROOT / "data" / "progress.json"


def empty_progress() -> dict[str, Any]:
    return {"version": 1, "questions": {}, "exam_attempts": []}


def load_progress(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_PROGRESS_PATH
    if not path.exists():
        return empty_progress()
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("version", 1)
    data.setdefault("questions", {})
    data.setdefault("exam_attempts", [])
    return data


def save_progress(data: dict[str, Any], path: Path | None = None) -> None:
    path = path or DEFAULT_PROGRESS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def reset_progress(path: Path | None = None) -> dict[str, Any]:
    data = empty_progress()
    save_progress(data, path)
    return data


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def record_answer(
    progress: dict[str, Any],
    question_id: str,
    is_correct: bool,
    *,
    at: str | None = None,
) -> dict[str, Any]:
    """Обновляет счётчики по id. Мутирует и возвращает progress."""
    questions = progress.setdefault("questions", {})
    entry = questions.get(question_id) or {
        "shown": 0,
        "correct": 0,
        "last_correct": False,
        "last_at": None,
    }
    entry["shown"] = int(entry.get("shown", 0)) + 1
    if is_correct:
        entry["correct"] = int(entry.get("correct", 0)) + 1
    else:
        entry["correct"] = int(entry.get("correct", 0))
    entry["last_correct"] = bool(is_correct)
    entry["last_at"] = at or _now_iso()
    questions[question_id] = entry
    return progress


def record_exam_attempt(
    progress: dict[str, Any],
    *,
    n: int,
    correct: int,
    disciplines: list[str],
    at: str | None = None,
    pass_threshold: float = 0.80,
) -> dict[str, Any]:
    pct = round(100.0 * correct / n, 1) if n else 0.0
    attempt = {
        "at": at or _now_iso(),
        "n": n,
        "correct": correct,
        "pct": pct,
        "passed": (correct / n) >= pass_threshold if n else False,
        "disciplines": list(disciplines),
    }
    progress.setdefault("exam_attempts", []).append(attempt)
    return progress


def stats_by_discipline(
    progress: dict[str, Any],
    questions: list[Question],
) -> list[dict[str, Any]]:
    """Агрегат % по дисциплинам (только вопросы с shown > 0)."""
    by_disc: dict[str, list[Question]] = {}
    for q in questions:
        by_disc.setdefault(q.discipline, []).append(q)

    rows: list[dict[str, Any]] = []
    qprog = progress.get("questions") or {}
    for disc, qs in by_disc.items():
        shown = correct = 0
        for q in qs:
            e = qprog.get(q.id)
            if not e:
                continue
            shown += int(e.get("shown", 0))
            correct += int(e.get("correct", 0))
        if shown == 0:
            continue
        rows.append(
            {
                "discipline": disc,
                "shown": shown,
                "correct": correct,
                "pct": round(100.0 * correct / shown, 1),
            }
        )
    rows.sort(key=lambda r: r["pct"])
    return rows


def weak_topics(
    progress: dict[str, Any],
    questions: list[Question],
    *,
    min_shown: int = 2,
    limit: int = 15,
) -> list[dict[str, Any]]:
    """Слабые темы (topic): min_shown показов, сортировка по accuracy."""
    by_topic: dict[tuple[str, str], dict[str, int]] = {}
    qprog = progress.get("questions") or {}
    for q in questions:
        e = qprog.get(q.id)
        if not e:
            continue
        key = (q.discipline, q.topic)
        bucket = by_topic.setdefault(key, {"shown": 0, "correct": 0})
        bucket["shown"] += int(e.get("shown", 0))
        bucket["correct"] += int(e.get("correct", 0))

    rows: list[dict[str, Any]] = []
    for (disc, topic), bucket in by_topic.items():
        if bucket["shown"] < min_shown:
            continue
        acc = bucket["correct"] / bucket["shown"]
        rows.append(
            {
                "discipline": disc,
                "topic": topic,
                "shown": bucket["shown"],
                "correct": bucket["correct"],
                "pct": round(100.0 * acc, 1),
            }
        )
    rows.sort(key=lambda r: (r["pct"], -r["shown"]))
    return rows[:limit]
