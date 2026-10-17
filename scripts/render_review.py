"""Validate questions/*.json and render questions/review/*.md for manual checking."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QDIR = ROOT / "questions"
OUT = QDIR / "review"
STATUS_RU = {
    "confirmed": "подтвержден",
    "corrected": "исправлен",
    "found": "найден",
    "unverified": "не подтвержден",
    "disputed": "спорный",
    "lecture": "по конспекту (в книге/НПА не найдено)",
}


def validate(q, errors):
    qid = q.get("id", "?")
    for field in ("id", "topic", "type", "stem", "options", "answer", "explanation", "source", "origin"):
        if field not in q:
            errors.append(f"{qid}: нет поля {field}")
    if q.get("answer") not in q.get("options", {}):
        errors.append(f"{qid}: ответ {q.get('answer')} отсутствует в options")
    if q.get("type") == "combo":
        letters = set(q.get("items", {}))
        for key, combo in q["options"].items():
            used = {x.strip() for x in combo.split(",")}
            if not used <= letters:
                errors.append(f"{qid}: вариант {key} ссылается на {used - letters}")
        if len(set(q["options"].values())) != len(q["options"]):
            errors.append(f"{qid}: повторяющиеся комбинации")
    if q.get("origin", {}).get("status") not in STATUS_RU:
        errors.append(f"{qid}: неизвестный статус")


def render_question(q):
    lines = [f"### {q['id']} · {q['topic']}", "", q["stem"], ""]
    if q["type"] == "combo":
        lines += [f"- {k}) {v}" for k, v in q["items"].items()]
        lines.append("")
    lines += [f"{k}) {v}" for k, v in q["options"].items()]
    origin = q["origin"]
    lines += [
        "",
        f"**Ответ:** {q['answer']}) {q['options'][q['answer']]}",
        f"**Пояснение:** {q['explanation']}",
        f"**Источник:** {q['source']}",
        f"**Из файла:** {origin['item']} — {STATUS_RU[origin['status']]}"
        + (f". {origin['note']}" if origin.get("note") else ""),
        "",
    ]
    return lines


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    errors, corrections, pending_all, lecture = [], [], [], []
    stats = Counter()
    for path in sorted(QDIR.glob("d*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        ids = [q["id"] for q in data["questions"]]
        for dup in {i for i in ids if ids.count(i) > 1}:
            errors.append(f"{path.name}: дубль id {dup}")
        md = [f"# {data['discipline']}", "", f"Вопросов: {len(data['questions'])}", ""]
        for q in data["questions"]:
            validate(q, errors)
            stats[q["origin"]["status"]] += 1
            md += render_question(q)
            if q["origin"]["status"] in ("corrected", "unverified", "disputed"):
                corrections.append((data["discipline"], q))
            elif q["origin"]["status"] == "lecture":
                lecture.append((data["discipline"], q))
        for p in data.get("pending", []):
            if p["status"] != "confirmed":
                pending_all.append((data["discipline"], p))
        (OUT / f"{path.stem}.md").write_text("\n".join(md), encoding="utf-8")
        stats["_total"] += len(data["questions"])

    md = ["# Исправленные и непроверенные ответы", "",
          "Прочитайте в первую очередь: здесь ответы из исходного файла, которые изменены или не подтверждены.", ""]
    md += ["## Исправленные", ""]
    for disc, q in corrections:
        md.append(f"- **{q['origin']['item']}** ({disc}, `{q['id']}`): {q['origin'].get('note', '')} "
                  f"Верно: {q['options'][q['answer']]}.")
    md += ["", "## Вопросы по конспекту (в книге и НПА не найдено — сверьте с лекцией)", ""]
    for disc, q in lecture:
        md.append(f"- **{q['origin']['item']}** ({disc}, `{q['id']}`): {q['stem']} — {q['options'][q['answer']]}")
    md += ["", "## Без вопроса: не подтверждено или спорно", ""]
    for disc, p in pending_all:
        md.append(f"- **{p['item']}** ({disc}) — {STATUS_RU[p['status']]}. «{p['text']}». {p['note']}")
    (OUT / "corrections.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("Всего вопросов:", stats.pop("_total"))
    print("Статусы:", dict(stats))
    print("Без вопроса (pending):", len(pending_all))
    if errors:
        print("ОШИБКИ:", *errors, sep="\n  ")
        sys.exit(1)
    print("Ошибок нет")


if __name__ == "__main__":
    main()
