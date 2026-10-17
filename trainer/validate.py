"""Валидация вопросов (правила зеркалят scripts/render_review.py)."""

from __future__ import annotations

from typing import Any

ALLOWED_TYPES = frozenset({"combo", "single", "yesno"})
ALLOWED_STATUSES = frozenset(
    {"confirmed", "corrected", "found", "unverified", "disputed", "lecture"}
)
REQUIRED_FIELDS = (
    "id",
    "topic",
    "type",
    "stem",
    "options",
    "answer",
    "explanation",
    "source",
    "origin",
)


def validate_question(q: dict[str, Any], errors: list[str], *, file_label: str = "") -> None:
    """Добавляет сообщения об ошибках в errors. file_label — имя файла для контекста."""
    prefix = f"{file_label}: " if file_label else ""
    qid = q.get("id", "?")
    label = f"{prefix}{qid}"

    for field in REQUIRED_FIELDS:
        if field not in q:
            errors.append(f"{label}: нет поля {field}")

    options = q.get("options")
    if not isinstance(options, dict) or not options:
        errors.append(f"{label}: options должен быть непустым объектом")
        return

    answer = q.get("answer")
    if answer not in options:
        errors.append(f"{label}: ответ {answer!r} отсутствует в options")

    qtype = q.get("type")
    if qtype not in ALLOWED_TYPES:
        errors.append(f"{label}: неизвестный type {qtype!r}")

    if qtype == "yesno" and len(options) != 2:
        errors.append(f"{label}: yesno должен иметь ровно 2 варианта")

    if qtype == "combo":
        items = q.get("items")
        if not isinstance(items, dict) or not items:
            errors.append(f"{label}: combo требует непустой items")
        else:
            letters = set(items)
            for key, combo in options.items():
                used = {x.strip() for x in str(combo).split(",") if x.strip()}
                if not used <= letters:
                    errors.append(f"{label}: вариант {key} ссылается на {used - letters}")
            if len(set(options.values())) != len(options):
                errors.append(f"{label}: повторяющиеся комбинации")

    origin = q.get("origin")
    if isinstance(origin, dict):
        status = origin.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{label}: неизвестный статус {status!r}")
    elif "origin" in q:
        errors.append(f"{label}: origin должен быть объектом")


def validate_bank(
    files: list[tuple[str, dict[str, Any]]],
) -> list[str]:
    """
    files — список (имя_файла, данные JSON).
    Проверяет вопросы и дубликаты id между файлами.
    """
    errors: list[str] = []
    seen_ids: dict[str, str] = {}

    for file_name, data in files:
        questions = data.get("questions")
        if not isinstance(questions, list):
            errors.append(f"{file_name}: нет массива questions")
            continue

        local_ids = [q.get("id") for q in questions if isinstance(q, dict)]
        for dup in {i for i in local_ids if i and local_ids.count(i) > 1}:
            errors.append(f"{file_name}: дубль id {dup}")

        for q in questions:
            if not isinstance(q, dict):
                errors.append(f"{file_name}: элемент questions не объект")
                continue
            validate_question(q, errors, file_label=file_name)
            qid = q.get("id")
            if qid:
                if qid in seen_ids:
                    errors.append(
                        f"{file_name}: дубль id {qid} (уже в {seen_ids[qid]})"
                    )
                else:
                    seen_ids[qid] = file_name

    return errors
