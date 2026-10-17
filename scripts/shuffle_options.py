"""Shuffle answer options in questions/*.json.

Authoring convention: write the correct option as "1". This script moves it to a
stable pseudo-random position (seeded by question id). Questions whose answer is
not "1" and yes/no questions are left untouched, so re-running is safe.
"""
import json
import random
from pathlib import Path

QDIR = Path(__file__).resolve().parent.parent / "questions"


def shuffle(q):
    if q["type"] == "yesno" or q["answer"] != "1":
        return False
    keys = list(q["options"])
    values = [q["options"][k] for k in keys]
    correct = values[0]
    rng = random.Random(q["id"])
    target = rng.randrange(len(values))
    rng.shuffle(values)
    values.remove(correct)
    values.insert(target, correct)
    q["options"] = dict(zip(keys, values))
    q["answer"] = keys[target]
    return True


def add_decoy(q):
    """Break the "longest option except 'all items' is correct" pattern.

    If no wrong option has as many letters as the correct one, replace the
    shortest wrong option with a same-length combo that swaps one correct
    letter for a wrong one.
    """
    if q["type"] != "combo":
        return False
    order = list(q["items"])
    parse = lambda s: [x.strip() for x in s.split(",")]
    correct = parse(q["options"][q["answer"]])
    wrong_letters = [x for x in order if x not in correct]
    others = {k: parse(v) for k, v in q["options"].items() if k != q["answer"]}
    partial = {k: v for k, v in others.items() if len(v) < len(order)}
    if not wrong_letters or not partial or any(len(v) == len(correct) for v in others.values()):
        return False
    rng = random.Random(q["id"] + "-decoy")
    decoy = list(correct)
    decoy.remove(rng.choice(correct))
    decoy.append(rng.choice(wrong_letters))
    decoy_str = ", ".join(sorted(decoy, key=order.index))
    if decoy_str in q["options"].values():
        return False
    victim = min(partial, key=lambda k: len(partial[k]))
    q["options"][victim] = decoy_str
    return True


def main():
    for path in sorted(QDIR.glob("d*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        decoys = sum(add_decoy(q) for q in data["questions"])
        changed = sum(shuffle(q) for q in data["questions"])
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(path.name, "перемешано:", changed, "добавлено ловушек:", decoys)


if __name__ == "__main__":
    main()
