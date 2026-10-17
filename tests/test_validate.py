from __future__ import annotations

import copy

from trainer.validate import validate_bank, validate_question


def test_valid_sample_bank(sample_data):
    errors = validate_bank([("sample_bank.json", sample_data)])
    assert errors == []


def test_bad_answer_key(sample_data):
    data = copy.deepcopy(sample_data)
    data["questions"][0]["answer"] = "9"
    errors = validate_bank([("sample_bank.json", data)])
    assert any("отсутствует в options" in e for e in errors)


def test_combo_letter_outside_items(sample_data):
    data = copy.deepcopy(sample_data)
    data["questions"][0]["options"]["1"] = "а, б, д"
    errors = validate_bank([("sample_bank.json", data)])
    assert any("ссылается на" in e for e in errors)


def test_duplicate_ids_across_files(sample_data):
    other = copy.deepcopy(sample_data)
    errors = validate_bank(
        [("a.json", sample_data), ("b.json", other)]
    )
    assert any("дубль id" in e for e in errors)


def test_yesno_must_have_two_options():
    q = {
        "id": "x-1",
        "topic": "t",
        "type": "yesno",
        "stem": "?",
        "options": {"1": "Да", "2": "Нет", "3": "Может"},
        "answer": "1",
        "explanation": "e",
        "source": "s",
        "origin": {"item": "i", "status": "confirmed"},
    }
    errors: list[str] = []
    validate_question(q, errors)
    assert any("ровно 2" in e for e in errors)
