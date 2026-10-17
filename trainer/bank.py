"""Загрузка банка вопросов из questions/d*.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trainer.validate import validate_bank

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUESTIONS_DIR = ROOT / "questions"


@dataclass
class Question:
    """Вопрос с привязкой к дисциплине и файлу."""

    id: str
    topic: str
    type: str
    stem: str
    options: dict[str, str]
    answer: str
    explanation: str
    source: str
    origin: dict[str, Any]
    discipline: str
    file_stem: str
    items: dict[str, str] | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, q: dict[str, Any], *, discipline: str, file_stem: str) -> Question:
        return cls(
            id=q["id"],
            topic=q["topic"],
            type=q["type"],
            stem=q["stem"],
            options=dict(q["options"]),
            answer=str(q["answer"]),
            explanation=q["explanation"],
            source=q["source"],
            origin=dict(q["origin"]),
            discipline=discipline,
            file_stem=file_stem,
            items=dict(q["items"]) if q.get("items") else None,
            raw=q,
        )

    def copy_for_session(self) -> Question:
        """Глубокая копия полей, меняемых при показе (options/answer)."""
        return Question(
            id=self.id,
            topic=self.topic,
            type=self.type,
            stem=self.stem,
            options=dict(self.options),
            answer=self.answer,
            explanation=self.explanation,
            source=self.source,
            origin=dict(self.origin),
            discipline=self.discipline,
            file_stem=self.file_stem,
            items=dict(self.items) if self.items else None,
            raw=self.raw,
        )


@dataclass
class Bank:
    questions: list[Question]
    disciplines: list[str]  # уникальные, в порядке файлов
    errors: list[str]

    def by_discipline(self, disciplines: list[str] | None = None) -> list[Question]:
        if not disciplines:
            return list(self.questions)
        wanted = set(disciplines)
        return [q for q in self.questions if q.discipline in wanted]

    def discipline_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for q in self.questions:
            counts[q.discipline] = counts.get(q.discipline, 0) + 1
        return counts


def load_raw_files(questions_dir: Path | None = None) -> list[tuple[str, dict[str, Any]]]:
    qdir = questions_dir or DEFAULT_QUESTIONS_DIR
    files: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(qdir.glob("d*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        files.append((path.name, data))
    return files


def load_all(questions_dir: Path | None = None) -> Bank:
    """Загружает все d*.json; pending не попадает в пул. Не пишет на диск."""
    raw_files = load_raw_files(questions_dir)
    errors = validate_bank(raw_files)

    questions: list[Question] = []
    disciplines: list[str] = []
    seen_disc: set[str] = set()

    for file_name, data in raw_files:
        discipline = data.get("discipline", file_name)
        stem = Path(file_name).stem
        if discipline not in seen_disc:
            disciplines.append(discipline)
            seen_disc.add(discipline)
        for q in data.get("questions") or []:
            if not isinstance(q, dict):
                continue
            questions.append(
                Question.from_dict(q, discipline=discipline, file_stem=stem)
            )

    return Bank(questions=questions, disciplines=disciplines, errors=errors)
