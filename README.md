# Тренажёр: аттестат специалиста рынка ЦБ (РБ)

Локальное приложение на **Python + Streamlit** для подготовки к тестированию на квалификационный аттестат 1-й категории специалиста рынка ценных бумаг Республики Беларусь.

Банк вопросов: `questions/d*.json` (новые файлы подхватываются автоматически). Прогресс хранится локально в `data/progress.json` и в git не попадает.

Репозиторий: https://github.com/Vladislav-Nikita/trenazher-cb-rb

## Быстрый старт (один файл)

Нужен установленный **Python 3.10+** (проверка: `python --version`).

В PowerShell из корня репозитория:

```powershell
powershell -ExecutionPolicy Bypass -File .\init.ps1
```

Скрипт создаёт `.venv`, ставит зависимости из `requirements.txt` (только Streamlit). Для тестов (`-Test`) дополнительно ставится `requirements-dev.txt` (pytest).

Запуск тренажёра сразу после инициализации:

```powershell
powershell -ExecutionPolicy Bypass -File .\init.ps1 -Start
```

Проверка тестов:

```powershell
powershell -ExecutionPolicy Bypass -File .\init.ps1 -Test
```

После инициализации можно запускать так:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

Откроется браузер: http://localhost:8501

## Облако (доступ с iPhone)

Можно открыть тренажёр с телефона без домашнего ПК через [Streamlit Community Cloud](https://share.streamlit.io):

1. Запушьте актуальный `main` в GitHub: https://github.com/Vladislav-Nikita/trenazher-cb-rb
2. Войдите на [share.streamlit.io](https://share.streamlit.io) через GitHub.
3. **New app** → репозиторий `Vladislav-Nikita/trenazher-cb-rb`, ветка `main`, Main file path: `app.py` → **Deploy**.
4. Откройте выданный URL (`https://….streamlit.app`) в Safari на iPhone; при желании добавьте на экран «Домой».

Замечания:

- Первый заход после простоя может занять 30–60+ секунд (бесплатный тариф «засыпает»).
- Прогресс в облаке **отдельный** от локального `data/progress.json` и может сбрасываться при перезапуске контейнера.
- Если репозиторий приватный — в Cloud дайте доступ к private repos (на бесплатном тарифе — один private app).

## Клонирование на другом компьютере

```powershell
git clone https://github.com/Vladislav-Nikita/trenazher-cb-rb.git
cd trenazher-cb-rb
powershell -ExecutionPolicy Bypass -File .\init.ps1 -Start
```

Обновление с GitHub:

```powershell
git pull
powershell -ExecutionPolicy Bypass -File .\init.ps1
```

## Режимы

| Режим | Что делает |
|--------|------------|
| Тренировка | Сразу верно/неверно, пояснение и источник |
| Экзамен | Без подсказок; в конце %; «сдано» при ≥80% |
| Работа над ошибками | Вопросы, где хотя бы раз ошибались |
| Слабые темы | Приоритет вопросов с низкой долей правильных |

## Клавиатура (в сессии)

| Клавиши | Действие |
|---------|----------|
| `←` `→` | Предыдущий / следующий вопрос |
| `1`–`4` | Выбрать вариант ответа |
| `Enter` | Тренировка: ответить → показать пояснение; второй Enter — далее. Экзамен: принять ответ и перейти дальше |

Если клавиши не срабатывают — кликните по области вопроса (фокус страницы).

## Структура

```
app.py              # интерфейс Streamlit
init.ps1            # полная инициализация (venv + pip)
trainer/            # загрузка банка, выбор вопросов, прогресс
questions/          # банк d*.json (+ review/)
scripts/            # render_review.py, shuffle_options.py
knowledge/          # карточки тем (опционально)
tests/              # pytest
requirements.txt    # runtime (Streamlit / Community Cloud)
requirements-dev.txt # + pytest для локальных тестов
data/               # progress.json (локально, в .gitignore)
```

## Важно

- Приложение **не меняет** исходные JSON.
- PDF/pptx курса в репозиторий не входят.
- Новые дисциплины: положите `questions/dNN_*.json` и перезапустите Streamlit.
