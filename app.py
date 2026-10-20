"""Тренажёр к аттестату специалиста рынка ценных бумаг (РБ), 1-я категория."""

from __future__ import annotations

import html

import streamlit as st
import streamlit.components.v1 as components

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
        "pending_choice": None,
        "kb_nonce": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


@st.cache_resource
def get_bank() -> Bank:
    return load_all()


def _radio_key(q: Question) -> str:
    return f"radio_{q.id}_{st.session_state.session_index}"


def _current_choice(q: Question) -> str | None:
    rkey = _radio_key(q)
    if rkey in st.session_state and st.session_state[rkey] is not None:
        return str(st.session_state[rkey])
    pending = st.session_state.get("pending_choice")
    if pending is not None and pending in q.options:
        return str(pending)
    saved = st.session_state.session_answers.get(q.id)
    if saved is not None and saved in q.options:
        return str(saved)
    return None


def _set_choice_callback(opt_key: str) -> None:
    """on_click до виджетов. На экране пояснения цифры игнорируем."""
    if st.session_state.get("awaiting_next"):
        return
    questions = st.session_state.get("session_questions") or []
    idx = int(st.session_state.get("session_index", 0))
    if not questions or idx < 0 or idx >= len(questions):
        return
    q: Question = questions[idx]
    if opt_key not in q.options:
        return
    st.session_state.pending_choice = opt_key
    st.session_state[_radio_key(q)] = opt_key


def _go_to_index(idx: int) -> None:
    questions = st.session_state.session_questions
    if not questions:
        return
    st.session_state.session_index = max(0, min(len(questions) - 1, int(idx)))
    st.session_state.awaiting_next = False
    st.session_state.last_feedback = None
    st.session_state.pending_choice = None


def _navigate(delta: int) -> None:
    _go_to_index(int(st.session_state.session_index) + delta)


def _exit_to_menu() -> None:
    st.session_state.view = "home"
    st.session_state.awaiting_next = False
    st.session_state.last_feedback = None
    st.session_state.pending_choice = None
    st.session_state.kb_nonce = int(st.session_state.get("kb_nonce", 0)) + 1


def _advance_after_feedback() -> None:
    """После пояснения — следующий вопрос. Домой сами не уходим."""
    total = len(st.session_state.session_questions)
    st.session_state.awaiting_next = False
    st.session_state.last_feedback = None
    st.session_state.pending_choice = None
    idx = int(st.session_state.session_index)
    if idx + 1 < total:
        st.session_state.session_index = idx + 1


def _submit_training(q: Question, choice: str) -> None:
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
    st.session_state.pending_choice = None


def _submit_exam(q: Question, choice: str) -> None:
    questions: list[Question] = st.session_state.session_questions
    already = q.id in st.session_state.session_answers
    st.session_state.session_answers[q.id] = choice
    if not already:
        progress = load_progress()
        record_answer(progress, q.id, choice == q.answer)
        save_progress(progress)
    st.session_state.pending_choice = None
    st.session_state.awaiting_next = False
    st.session_state.last_feedback = None

    if len(st.session_state.session_answers) >= len(questions):
        _finish_exam()
        return

    idx = int(st.session_state.session_index)
    if idx + 1 < len(questions):
        st.session_state.session_index = idx + 1


def _on_enter_key() -> None:
    if st.session_state.get("awaiting_next"):
        _advance_after_feedback()
        return
    questions = st.session_state.get("session_questions") or []
    idx = int(st.session_state.get("session_index", 0))
    if not questions or idx >= len(questions):
        return
    q: Question = questions[idx]
    choice = _current_choice(q)
    if choice is None:
        return
    mode = Mode(st.session_state.session_mode)
    if mode == Mode.EXAM:
        _submit_exam(q, choice)
    else:
        # Повторный Enter на уже отвеченном без экрана пояснения — к следующему
        if q.id in st.session_state.session_answers and not st.session_state.awaiting_next:
            if idx + 1 < len(questions):
                _go_to_index(idx + 1)
            return
        _submit_training(q, choice)


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
    st.session_state.pending_choice = None
    st.session_state.kb_nonce = int(st.session_state.get("kb_nonce", 0)) + 1
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


def _mobile_touch_css() -> str:
    """Стили для узкого экрана / пальца: крупные тапы, скрыть подсказки клавиатуры."""
    return """
        @media (max-width: 640px), (pointer: coarse) {
            .kb-hint { display: none !important; }
            section.main > div.block-container,
            div.block-container,
            [data-testid="stMainBlockContainer"] {
                padding-left: 0.55rem !important;
                padding-right: 0.55rem !important;
            }
            .q-stem, .q-stem p, .q-items, .q-items li, .q-items p {
                font-size: 1.05rem !important; line-height: 1.4 !important;
            }
            div[data-testid="stRadio"] label,
            div[data-testid="stRadio"] label p {
                font-size: 1.05rem !important; line-height: 1.35 !important;
            }
            div[data-testid="stRadio"] label {
                min-height: 2.75rem !important;
                padding-top: 0.35rem !important;
                padding-bottom: 0.35rem !important;
            }
            div[data-testid="stRadio"] [role="radiogroup"] { gap: 0.35rem !important; }
            .st-key-btn_exit_menu button,
            .st-key-btn_nav_prev button,
            .st-key-btn_nav_next button {
                min-height: 2.75rem !important; height: 2.75rem !important;
                padding: 0 0.75rem !important; font-size: 0.95rem !important;
            }
            .st-key-btn_answer button,
            .st-key-btn_exam_next button,
            .st-key-btn_feedback_next button,
            .st-key-btn_home_start button,
            .st-key-btn_home_stats button {
                min-height: 2.85rem !important;
                font-size: 1.05rem !important;
            }
            .qnav a {
                width: 2rem !important; height: 2rem !important;
                font-size: 0.8rem !important;
            }
            .qnav { gap: 5px !important; }
        }
    """


def _session_chrome_css() -> None:
    st.markdown(
        f"""
        <style>
        /* Жёстко убрать верхний запас Streamlit */
        html, body {{ margin: 0 !important; padding: 0 !important; }}
        header[data-testid="stHeader"],
        div[data-testid="stDecoration"],
        div[data-testid="stToolbar"],
        .stAppDeployButton,
        [data-testid="stStatusWidget"],
        #MainMenu {{ display: none !important; }}
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        section.main {{
            padding-top: 0 !important;
            margin-top: 0 !important;
        }}
        .stApp > header {{ display: none !important; }}
        section.main > div.block-container,
        div.block-container,
        [data-testid="stMainBlockContainer"] {{
            padding-top: 0.15rem !important;
            padding-bottom: 0.5rem !important;
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            max-width: 48rem !important;
        }}
        section.main [data-testid="stVerticalBlock"] {{ gap: 0.2rem !important; }}
        section.main [data-testid="stHorizontalBlock"] {{ gap: 0.25rem !important; }}
        div[data-testid="stSidebar"] {{ display: none !important; }}
        button[kind="header"] {{ display: none !important; }}

        /* Скрыть хоткеи и их iframe-обёртки */
        .st-key-kb_left, .st-key-kb_right, .st-key-kb_enter,
        .st-key-kb_opt_1, .st-key-kb_opt_2, .st-key-kb_opt_3, .st-key-kb_opt_4 {{
            display: none !important; height: 0 !important; margin: 0 !important;
        }}
        iframe[height="0"], iframe[height="0px"] {{
            display: none !important; height: 0 !important; border: 0 !important;
        }}
        div:has(> iframe[height="0"]), div:has(> iframe[height="0px"]) {{
            display: none !important; height: 0 !important; margin: 0 !important;
            padding: 0 !important; min-height: 0 !important;
        }}

        .st-key-btn_exit_menu button,
        .st-key-btn_nav_prev button,
        .st-key-btn_nav_next button {{
            min-height: 1.55rem !important; height: 1.55rem !important;
            padding: 0 0.5rem !important; font-size: 0.78rem !important;
        }}

        /* Плотная HTML-навигация по вопросам */
        .qnav {{
            display: flex; flex-wrap: wrap; gap: 3px;
            margin: 0.15rem 0 0.35rem 0; align-items: center;
        }}
        .qnav a {{
            display: inline-flex; align-items: center; justify-content: center;
            width: 1.55rem; height: 1.55rem; box-sizing: border-box;
            border: 1px solid rgba(128,128,128,0.55); border-radius: 4px;
            font-size: 0.72rem; text-decoration: none; color: inherit;
            background: transparent; line-height: 1;
        }}
        .qnav a.answered {{
            background: #2e7d32; border-color: #2e7d32; color: #fff;
        }}
        .qnav a.current {{
            outline: 2px solid #f44336; outline-offset: 1px;
        }}

        .q-stem, .q-stem p, .q-items, .q-items li, .q-items p,
        div[data-testid="stRadio"] label, div[data-testid="stRadio"] label p {{
            font-size: 1.2rem !important; line-height: 1.35 !important;
        }}
        .q-stem {{ margin: 0.1rem 0 0.25rem 0 !important; }}
        .q-items {{
            margin: 0.1rem 0 0.3rem 0 !important;
            padding-left: 1.1rem !important;
        }}
        div[data-testid="stRadio"] [role="radiogroup"] {{ gap: 0.1rem !important; }}
        div[data-testid="stAlert"] {{
            padding: 0.3rem 0.6rem !important; margin: 0.15rem 0 !important;
        }}
        div[data-testid="stAlert"] p {{ font-size: 1.05rem !important; }}
        {_mobile_touch_css()}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _home_chrome_css() -> None:
    st.markdown(
        f"""
        <style>
        section.main > div.block-container,
        div.block-container,
        [data-testid="stMainBlockContainer"] {{
            max-width: 48rem !important;
        }}
        {_mobile_touch_css()}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _apply_nav_query_param() -> None:
    """Переход по клику на номер: ?q=N (1-based)."""
    raw = st.query_params.get("q")
    if raw is None:
        return
    try:
        num = int(raw)
    except (TypeError, ValueError):
        st.query_params.clear()
        return
    questions = st.session_state.get("session_questions") or []
    if questions and 1 <= num <= len(questions):
        _go_to_index(num - 1)
    st.query_params.clear()


def _render_session_toolbar(questions: list[Question]) -> None:
    """«В меню» + ←/→ + плотная HTML-сетка номеров."""
    answers = st.session_state.session_answers
    cur = int(st.session_state.session_index)
    total = len(questions)

    menu_col, prev_col, next_col, _ = st.columns([1.4, 0.55, 0.55, 4.5])
    with menu_col:
        if st.button("В меню", key="btn_exit_menu"):
            _exit_to_menu()
            st.rerun()
    with prev_col:
        if st.button("←", key="btn_nav_prev", disabled=cur <= 0):
            _navigate(-1)
            st.rerun()
    with next_col:
        if st.button("→", key="btn_nav_next", disabled=cur >= total - 1):
            _navigate(1)
            st.rerun()

    cells = []
    for i, q in enumerate(questions):
        classes = []
        if q.id in answers:
            classes.append("answered")
        if i == cur:
            classes.append("current")
        cls = (" " + " ".join(classes)) if classes else ""
        cells.append(f'<a class="{cls.strip()}" href="?q={i + 1}">{i + 1}</a>')
    st.markdown(f'<div class="qnav">{"".join(cells)}</div>', unsafe_allow_html=True)


def _render_status_banner(q: Question) -> None:
    status = (q.origin or {}).get("status")
    if status not in STATUS_WARN:
        return
    if status == "lecture":
        st.warning("По конспекту — сверить с лекцией.")
    else:
        st.warning("Спорный вопрос — сверить с источником.")


def _render_question_body(q: Question) -> str | None:
    st.markdown(
        f'<div class="q-stem">{html.escape(q.stem)}</div>',
        unsafe_allow_html=True,
    )
    _render_status_banner(q)

    if q.type == "combo" and q.items:
        items_html = "".join(
            f"<li><strong>{html.escape(letter)})</strong> {html.escape(text)}</li>"
            for letter, text in q.items.items()
        )
        st.markdown(f'<ul class="q-items">{items_html}</ul>', unsafe_allow_html=True)

    option_keys = list(q.options.keys())
    rkey = _radio_key(q)

    pending = st.session_state.get("pending_choice")
    if pending is not None and pending in q.options:
        st.session_state[rkey] = pending
        st.session_state.pending_choice = None
    elif rkey not in st.session_state:
        saved = st.session_state.session_answers.get(q.id)
        if saved in q.options:
            st.session_state[rkey] = saved

    radio_kw: dict = {
        "label": "Ответ",
        "options": option_keys,
        "format_func": lambda k: f"{k}) {q.options[k]}",
        "key": rkey,
        "label_visibility": "collapsed",
    }
    if rkey not in st.session_state:
        radio_kw["index"] = None
    return st.radio(**radio_kw)


def _bind_keyboard_shortcuts(shortcuts: dict[str, str]) -> None:
    """
    Свой биндинг с nonce: при повторном входе в сессию скрипт точно
    переустанавливается (streamlit-shortcuts иначе кэширует iframe).
    """
    import json

    nonce = int(st.session_state.get("kb_nonce", 0))
    payload = json.dumps(shortcuts, ensure_ascii=False)
    components.html(
        f"""
        <script>
        (function() {{
          const doc = window.parent.document;
          const win = window.parent.window;
          const shortcuts = {payload};
          const nonce = {nonce};

          if (win.__trenazherKbListener) {{
            doc.removeEventListener('keydown', win.__trenazherKbListener);
            win.__trenazherKbListener = null;
          }}

          win.__trenazherKbListener = function(e) {{
            if (e.repeat) return;
            const target = e.target;
            if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {{
              return;
            }}
            for (const [key, shortcut] of Object.entries(shortcuts)) {{
              const parts = String(shortcut).toLowerCase().split('+');
              const mainKey = parts.find(p => !['ctrl','alt','shift','meta','cmd'].includes(p));
              const needCtrl = parts.includes('ctrl');
              const needAlt = parts.includes('alt');
              const needShift = parts.includes('shift');
              const needMeta = parts.includes('meta') || parts.includes('cmd');
              if (needCtrl !== e.ctrlKey || needAlt !== e.altKey ||
                  needShift !== e.shiftKey || needMeta !== e.metaKey) continue;
              if (e.key.toLowerCase() !== mainKey) continue;
              e.preventDefault();
              const el = doc.querySelector('.st-key-' + key + ' button');
              if (el) {{ el.click(); }}
              return;
            }}
          }};
          doc.addEventListener('keydown', win.__trenazherKbListener);
          win.__trenazherKbNonce = nonce;
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def _render_kb_controls(q: Question) -> None:
    """Служебные кнопки + хоткеи (включая Esc → в меню)."""
    shortcuts: dict[str, str] = {
        "kb_left": "arrowleft",
        "kb_right": "arrowright",
        "kb_enter": "enter",
        "btn_exit_menu": "escape",
    }
    st.button("←", key="kb_left", on_click=_navigate, args=(-1,))
    st.button("→", key="kb_right", on_click=_navigate, args=(1,))
    for key in ("1", "2", "3", "4"):
        btn_key = f"kb_opt_{key}"
        shortcuts[btn_key] = key
        st.button(key, key=btn_key, on_click=_set_choice_callback, args=(key,))
    st.button("Enter", key="kb_enter", on_click=_on_enter_key)
    _bind_keyboard_shortcuts(shortcuts)


def _render_session() -> None:
    questions: list[Question] = st.session_state.session_questions
    if not questions:
        st.session_state.view = "home"
        return

    _session_chrome_css()
    _apply_nav_query_param()
    _render_session_toolbar(questions)

    idx = int(st.session_state.session_index)
    if idx < 0 or idx >= len(questions):
        st.session_state.session_index = 0
        idx = 0
    q = questions[idx]
    mode = Mode(st.session_state.session_mode)

    if st.session_state.awaiting_next and st.session_state.last_feedback:
        fb = st.session_state.last_feedback
        st.markdown(
            f'<div class="q-stem">{html.escape(q.stem)}</div>',
            unsafe_allow_html=True,
        )
        chosen = st.session_state.session_answers.get(q.id)
        if chosen is not None:
            st.caption(f"Ваш ответ: {chosen}) {q.options.get(chosen, '')}")
        if fb["ok"]:
            st.success("Верно")
        else:
            st.error("Неверно")
            st.markdown(f"**Верно:** {fb['answer_key']}) {fb['answer_text']}")
        st.markdown(fb["explanation"])
        st.caption(fb["source"])
        st.markdown(
            '<p class="kb-hint" style="margin:0.15rem 0;opacity:0.75;font-size:0.85rem;">'
            "ПК: Enter — далее · Esc — меню</p>",
            unsafe_allow_html=True,
        )
        if st.button("Далее", type="primary", key="btn_feedback_next", use_container_width=True):
            _advance_after_feedback()
            st.rerun()
        _render_kb_controls(q)
        return

    _render_question_body(q)

    choice = _current_choice(q)
    if mode == Mode.EXAM:
        if st.button(
            "Далее",
            type="primary",
            key="btn_exam_next",
            disabled=choice is None,
            use_container_width=True,
        ):
            if choice is not None:
                _submit_exam(q, choice)
                st.rerun()
    else:
        if st.button(
            "Ответить",
            type="primary",
            key="btn_answer",
            disabled=choice is None,
            use_container_width=True,
        ):
            if choice is not None:
                _submit_training(q, choice)
                st.rerun()
    st.markdown(
        '<p class="kb-hint" style="margin:0.1rem 0;opacity:0.75;font-size:0.85rem;">'
        "ПК: 1–4 выбор · Enter — ответить · ← → навигация · Esc — меню</p>",
        unsafe_allow_html=True,
    )
    # Хоткеи в конце — iframe не толкает контент вниз
    _render_kb_controls(q)


def _collect_disciplines(bank: Bank, key_prefix: str) -> list[str]:
    all_disc = bank.disciplines
    select_all = st.checkbox("Все дисциплины", value=True, key=f"{key_prefix}_all_disc")
    if select_all:
        return list(all_disc)
    return [
        d
        for d in all_disc
        if st.checkbox(
            f"{d} ({bank.discipline_counts().get(d, 0)})",
            value=False,
            key=f"{key_prefix}_disc_{d}",
        )
    ]


def _render_home_setup(bank: Bank) -> None:
    """Старт сессии на главной — без необходимости открывать sidebar."""
    st.markdown("#### Начать")
    disciplines = _collect_disciplines(bank, "home")

    mode_label = st.radio(
        "Режим",
        options=list(MODE_LABELS.values()),
        index=0,
        key="home_mode",
        horizontal=True,
    )
    mode = next(m for m, label in MODE_LABELS.items() if label == mode_label)

    default_n = DEFAULT_EXAM_N if mode == Mode.EXAM else 10
    n = st.number_input(
        "Количество вопросов",
        min_value=1,
        max_value=500,
        value=default_n,
        key="home_n",
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Начать", type="primary", key="btn_home_start", use_container_width=True):
            if not disciplines:
                st.error("Выберите хотя бы одну дисциплину.")
            else:
                _start_session(bank, mode, disciplines, int(n))
                st.rerun()
    with c2:
        if st.button("Статистика", key="btn_home_stats", use_container_width=True):
            st.session_state.view = "stats"
            st.rerun()


def _render_reset_controls(*, key_prefix: str) -> None:
    if st.session_state.confirm_reset:
        st.warning("Сбросить весь прогресс?")
        c1, c2 = st.columns(2)
        if c1.button("Да", key=f"{key_prefix}_reset_yes", use_container_width=True):
            reset_progress()
            st.session_state.confirm_reset = False
            st.success("Прогресс сброшен.")
            st.rerun()
        if c2.button("Нет", key=f"{key_prefix}_reset_no", use_container_width=True):
            st.session_state.confirm_reset = False
            st.rerun()
    elif st.button("Сбросить прогресс", key=f"{key_prefix}_reset", use_container_width=True):
        st.session_state.confirm_reset = True
        st.rerun()


def _render_setup_sidebar(bank: Bank) -> None:
    """Вторичные действия: сброс прогресса и справка (старт — на главной)."""
    with st.sidebar:
        st.header("Прогресс")
        _render_reset_controls(key_prefix="side")
        st.divider()
        st.caption("Тренажёр ЦБ РБ")
        st.caption(
            f"В банке: {len(bank.questions)} вопросов, {len(bank.disciplines)} дисциплин."
        )
        st.caption("Старт сессии — на главной странице.")


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

    if st.button("В меню"):
        _exit_to_menu()
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
    _home_chrome_css()
    st.title("Тренажёр: аттестат специалиста рынка ЦБ (РБ)")
    st.markdown(
        f"Порог сдачи экзамена — **{int(PASS_THRESHOLD * 100)}%**.\n\n"
        "На телефоне: выбор варианта и кнопки **Ответить** / **Далее** / **← →**.\n\n"
        '<span class="kb-hint">На ПК дополнительно: <strong>1–4</strong> выбор, '
        "<strong>Enter</strong> — ответить / далее, <strong>← →</strong> — навигация, "
        "<strong>Esc</strong> — меню.</span>",
        unsafe_allow_html=True,
    )
    if st.session_state.get("empty_mistakes"):
        st.warning("Пока нет ошибок — сначала потренируйтесь или сдайте экзамен.")
        st.session_state.empty_mistakes = False

    _render_home_setup(bank)

    with st.expander("Банк вопросов", expanded=False):
        counts = bank.discipline_counts()
        for disc in bank.disciplines:
            st.write(f"- {disc}: {counts.get(disc, 0)}")

    with st.expander("Сброс прогресса", expanded=False):
        _render_reset_controls(key_prefix="home")


def main() -> None:
    st.set_page_config(
        page_title="Тренажёр ЦБ РБ",
        page_icon="📘",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    _init_state()

    bank = get_bank()
    if bank.errors:
        st.error("Ошибки в банке вопросов — тренажёр не запущен:")
        for err in bank.errors:
            st.markdown(f"- {err}")
        st.stop()

    view = st.session_state.view
    if view == "session":
        _render_session()
    elif view == "exam_result":
        _render_setup_sidebar(bank)
        st.title("Тренажёр ЦБ РБ")
        _render_exam_result()
    elif view == "stats":
        _render_setup_sidebar(bank)
        st.title("Тренажёр ЦБ РБ")
        _render_stats(bank)
    else:
        _render_setup_sidebar(bank)
        _render_home(bank)


if __name__ == "__main__":
    main()
