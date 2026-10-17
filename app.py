"""Тренажёр к аттестату специалиста рынка ценных бумаг (РБ), 1-я категория."""

from __future__ import annotations

import streamlit as st

from trainer.bank import Bank, Question, load_all
from trainer.progress import (
    load_progress,
    record_answer,
    record_exam_attempt,
    reset_progress,
    save_progress,
    stats_by_discipline,
    weak_topics,
)
from trainer.select import DEFAULT_EXAM_N, Mode, PASS_THRESHOLD, select_questions

MODE_LABELS = {
    Mode.TRAINING: "Тренировка",
    Mode.EXAM: "Экзамен",
    Mode.MISTAKES: "Работа над ошибками",
    Mode.WEAK: "Слабые темы",
}

STATUS_WARN = frozenset({"lecture", "disputed"})


def _md_table(rows: list[dict]) -> None:
    """Таблица без pandas/pyarrow (st.dataframe/st.table их требуют)."""
    if not rows:
        return
    cols = list(rows[0].keys())

    def cell(value: object) -> str:
        text = str(value).replace("|", "\\|").replace("\n", " ")
        return text

    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = "\n".join(
        "| " + " | ".join(cell(row.get(c, "")) for c in cols) + " |" for row in rows
    )
    st.markdown("\n".join([header, sep, body]))


def _init_state() -> None:
    defaults = {
        "view": "home",  # home | session | stats | exam_result
        "session_questions": [],
        "session_index": 0,
        "session_mode": Mode.TRAINING.value,
        "session_answers": {},  # id -> chosen key
        "session_disciplines": [],
        "awaiting_next": False,
        "last_feedback": None,
        "confirm_reset": False,
        "empty_mistakes": False,
        "exam_summary": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


@st.cache_resource
def get_bank() -> Bank:
    return load_all()


def _render_status_banner(q: Question) -> None:
    status = (q.origin or {}).get("status")
    if status not in STATUS_WARN:
        return
    if status == "lecture":
        st.warning("По конспекту — сверить с лекцией (в книге/НПА не найдено).")
    else:
        st.warning("Спорный вопрос — сверить с лекцией / источником.")


def _render_question_body(q: Question) -> str | None:
    st.caption(f"{q.id} · {q.topic}")
    st.markdown(f"**{q.discipline}**")
    _render_status_banner(q)
    st.markdown(q.stem)

    if q.type == "combo" and q.items:
        st.markdown("**Пункты:**")
        for letter, text in q.items.items():
            st.markdown(f"- **{letter})** {text}")

    option_keys = list(q.options.keys())
    choice = st.radio(
        "Варианты ответа:" if q.type == "combo" else "Выберите ответ:",
        options=option_keys,
        format_func=lambda k: f"{k}) {q.options[k]}",
        key=f"radio_{q.id}_{st.session_state.session_index}",
        index=None,
    )
    return choice


def _start_session(bank: Bank, mode: Mode, disciplines: list[str], n: int) -> None:
    pool = bank.by_discipline(disciplines)
    progress = load_progress()
    chosen = select_questions(mode, pool, n, progress)

    if mode == Mode.MISTAKES and not chosen:
        st.session_state.view = "home"
        st.session_state.empty_mistakes = True
        return

    st.session_state.empty_mistakes = False
    st.session_state.session_questions = chosen
    st.session_state.session_index = 0
    st.session_state.session_mode = mode.value
    st.session_state.session_answers = {}
    st.session_state.session_disciplines = disciplines
    st.session_state.awaiting_next = False
    st.session_state.last_feedback = None
    st.session_state.view = "session"


def _finish_exam() -> None:
    questions: list[Question] = st.session_state.session_questions
    answers: dict[str, str] = st.session_state.session_answers
    correct_count = sum(1 for q in questions if answers.get(q.id) == q.answer)
    progress = load_progress()
    record_exam_attempt(
        progress,
        n=len(questions),
        correct=correct_count,
        disciplines=st.session_state.session_disciplines,
    )
    save_progress(progress)
    st.session_state.exam_summary = {
        "n": len(questions),
        "correct": correct_count,
        "pct": round(100.0 * correct_count / len(questions), 1) if questions else 0.0,
        "passed": (correct_count / len(questions)) >= PASS_THRESHOLD if questions else False,
        "errors": [q for q in questions if answers.get(q.id) != q.answer],
        "answers": dict(answers),
    }
    st.session_state.view = "exam_result"


def _render_sidebar(bank: Bank) -> None:
    with st.sidebar:
        st.header("Настройки")
        all_disc = bank.disciplines
        select_all = st.checkbox("Все дисциплины", value=True)
        if select_all:
            disciplines = list(all_disc)
        else:
            disciplines = [
                d
                for d in all_disc
                if st.checkbox(f"{d} ({bank.discipline_counts().get(d, 0)})", value=False, key=f"disc_{d}")
            ]

        mode_label = st.radio(
            "Режим",
            options=list(MODE_LABELS.values()),
            index=0,
        )
        mode = next(m for m, label in MODE_LABELS.items() if label == mode_label)

        default_n = DEFAULT_EXAM_N if mode == Mode.EXAM else 10
        n = st.number_input("Количество вопросов", min_value=1, max_value=500, value=default_n)

        if st.button("Начать", type="primary", use_container_width=True):
            if not disciplines:
                st.error("Выберите хотя бы одну дисциплину.")
            else:
                _start_session(bank, mode, disciplines, int(n))
                st.rerun()

        if st.button("Статистика", use_container_width=True):
            st.session_state.view = "stats"
            st.rerun()

        st.divider()
        if st.session_state.confirm_reset:
            st.warning("Сбросить весь прогресс?")
            c1, c2 = st.columns(2)
            if c1.button("Да", use_container_width=True):
                reset_progress()
                st.session_state.confirm_reset = False
                st.success("Прогресс сброшен.")
                st.rerun()
            if c2.button("Нет", use_container_width=True):
                st.session_state.confirm_reset = False
                st.rerun()
        elif st.button("Сбросить прогресс", use_container_width=True):
            st.session_state.confirm_reset = True
            st.rerun()

        st.caption(f"В банке: {len(bank.questions)} вопросов, {len(all_disc)} дисциплин.")


def _render_training_step(q: Question) -> None:
    mode = Mode(st.session_state.session_mode)
    idx = st.session_state.session_index
    total = len(st.session_state.session_questions)
    st.progress((idx) / total if total else 0)
    st.write(f"Вопрос {idx + 1} из {total}")

    if st.session_state.awaiting_next and st.session_state.last_feedback:
        fb = st.session_state.last_feedback
        if fb["ok"]:
            st.success("Верно")
        else:
            st.error("Неверно")
            st.markdown(f"**Правильный ответ:** {fb['answer_key']}) {fb['answer_text']}")
        st.markdown(f"**Пояснение:** {fb['explanation']}")
        st.caption(f"Источник: {fb['source']}")
        if st.button("Далее", type="primary"):
            st.session_state.awaiting_next = False
            st.session_state.last_feedback = None
            st.session_state.session_index += 1
            if st.session_state.session_index >= total:
                st.session_state.view = "home"
                st.info("Сессия завершена.")
            st.rerun()
        return

    choice = _render_question_body(q)
    if st.button("Ответить", type="primary", disabled=choice is None):
        is_ok = choice == q.answer
        progress = load_progress()
        record_answer(progress, q.id, is_ok)
        save_progress(progress)
        st.session_state.session_answers[q.id] = choice
        st.session_state.last_feedback = {
            "ok": is_ok,
            "answer_key": q.answer,
            "answer_text": q.options[q.answer],
            "explanation": q.explanation,
            "source": q.source,
        }
        st.session_state.awaiting_next = True
        st.rerun()


def _render_exam_step(q: Question) -> None:
    idx = st.session_state.session_index
    total = len(st.session_state.session_questions)
    st.progress(idx / total if total else 0)
    st.write(f"Вопрос {idx + 1} из {total} (экзамен — без подсказок)")

    choice = _render_question_body(q)
    if st.button("Далее", type="primary", disabled=choice is None):
        st.session_state.session_answers[q.id] = choice
        progress = load_progress()
        record_answer(progress, q.id, choice == q.answer)
        save_progress(progress)
        st.session_state.session_index += 1
        if st.session_state.session_index >= total:
            _finish_exam()
        st.rerun()


def _render_session() -> None:
    questions: list[Question] = st.session_state.session_questions
    if not questions:
        st.warning("Нет вопросов для сессии.")
        st.session_state.view = "home"
        return

    idx = st.session_state.session_index
    if idx >= len(questions):
        st.session_state.view = "home"
        return

    q = questions[idx]
    mode = Mode(st.session_state.session_mode)
    if mode == Mode.EXAM:
        _render_exam_step(q)
    else:
        # тренировка, ошибки, слабые темы — с мгновенной обратной связью
        _render_training_step(q)

    if st.button("Прервать сессию"):
        st.session_state.view = "home"
        st.session_state.awaiting_next = False
        st.rerun()


def _render_exam_result() -> None:
    summary = st.session_state.get("exam_summary")
    if not summary:
        st.session_state.view = "home"
        return

    pct = summary["pct"]
    st.subheader("Результат экзамена")
    st.metric("Правильных", f"{summary['correct']} / {summary['n']} ({pct}%)")
    if summary["passed"]:
        st.success(f"Сдано (≥ {int(PASS_THRESHOLD * 100)}%)")
    else:
        st.error(f"Не сдано (нужно ≥ {int(PASS_THRESHOLD * 100)}%)")

    errors: list[Question] = summary["errors"]
    answers = summary["answers"]
    if errors:
        st.markdown("### Разбор ошибок")
        for q in errors:
            with st.expander(f"{q.id} · {q.topic}"):
                st.markdown(q.stem)
                chosen = answers.get(q.id)
                st.markdown(f"**Ваш ответ:** {chosen}) {q.options.get(chosen, '—')}")
                st.markdown(f"**Верно:** {q.answer}) {q.options[q.answer]}")
                st.markdown(f"**Пояснение:** {q.explanation}")
                st.caption(f"Источник: {q.source}")
    else:
        st.info("Ошибок нет.")

    if st.button("На главный экран"):
        st.session_state.view = "home"
        st.rerun()


def _render_stats(bank: Bank) -> None:
    st.subheader("Статистика")
    progress = load_progress()

    rows = stats_by_discipline(progress, bank.questions)
    if rows:
        st.markdown("#### По дисциплинам")
        _md_table(
            [
                {
                    "Дисциплина": r["discipline"],
                    "Показов": r["shown"],
                    "Верных": r["correct"],
                    "%": r["pct"],
                }
                for r in rows
            ]
        )
    else:
        st.info("Пока нет ответов по дисциплинам.")

    weak = weak_topics(progress, bank.questions)
    st.markdown("#### Слабые темы (мин. 2 показа)")
    if weak:
        _md_table(
            [
                {
                    "Дисциплина": r["discipline"],
                    "Тема": r["topic"],
                    "Показов": r["shown"],
                    "%": r["pct"],
                }
                for r in weak
            ]
        )
    else:
        st.info("Недостаточно данных по темам.")

    attempts = progress.get("exam_attempts") or []
    st.markdown("#### Попытки экзамена")
    if attempts:
        _md_table(
            [
                {
                    "Дата": a.get("at", ""),
                    "Вопросов": a.get("n"),
                    "Верных": a.get("correct"),
                    "%": a.get("pct"),
                    "Сдано": "да" if a.get("passed") else "нет",
                }
                for a in reversed(attempts)
            ]
        )
    else:
        st.info("Попыток экзамена ещё не было.")

    if st.button("Назад"):
        st.session_state.view = "home"
        st.rerun()


def _render_home(bank: Bank) -> None:
    st.markdown(
        "Выберите дисциплины и режим в боковой панели, затем нажмите **Начать**.\n\n"
        f"Порог сдачи экзамена — **{int(PASS_THRESHOLD * 100)}%**. "
        "Варианты ответов перемешиваются при каждом показе."
    )
    if st.session_state.get("empty_mistakes"):
        st.warning("Пока нет ошибок — сначала потренируйтесь или сдайте экзамен.")
        st.session_state.empty_mistakes = False

    counts = bank.discipline_counts()
    st.markdown("#### Банк вопросов")
    for disc in bank.disciplines:
        st.write(f"- {disc}: {counts.get(disc, 0)}")


def main() -> None:
    st.set_page_config(page_title="Тренажёр ЦБ РБ", page_icon="📘", layout="centered")
    st.title("Тренажёр: аттестат специалиста рынка ЦБ (РБ)")
    _init_state()

    bank = get_bank()
    if bank.errors:
        st.error("Ошибки в банке вопросов — тренажёр не запущен:")
        for err in bank.errors:
            st.markdown(f"- {err}")
        st.stop()

    _render_sidebar(bank)

    view = st.session_state.view
    if view == "session":
        _render_session()
    elif view == "exam_result":
        _render_exam_result()
    elif view == "stats":
        _render_stats(bank)
    else:
        _render_home(bank)


if __name__ == "__main__":
    main()
