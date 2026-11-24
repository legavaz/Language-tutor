#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Создаёт пресеты «Напарника» и настраивает звук в Open WebUI.

Запуск:

    NAPARNIK_URL=https://192.168.1.10 \
    NAPARNIK_EMAIL=admin@example.com \
    NAPARNIK_PASSWORD='пароль' \
    python3 scripts/setup-preset.py

Создаются три модели:
    naparnik-tutor   — разговорный тьютор (по умолчанию)
    naparnik-drill   — тренажёр упражнений
    naparnik-level   — проверка уровня CEFR

Переменные окружения:
    NAPARNIK_URL        адрес приложения (по умолчанию http://127.0.0.1:3000)
    NAPARNIK_EMAIL      логин администратора (обязателен)
    NAPARNIK_PASSWORD   пароль администратора (обязателен)
    NAPARNIK_BASE_MODEL базовая модель (по умолчанию gemini-3.5-flash-lite)
    TTS_API_KEY         ключ между WebUI и naparnik-tts (по умолчанию naparnik-tts-local)
    TTS_VOICE           голос синтеза (по умолчанию en-US-AriaNeural)
    VERIFY_TLS          "false" — не проверять сертификат (внутренний CA Caddy)
"""

import json
import os
import ssl
import sys
import urllib.error
import urllib.request

URL = os.environ.get("NAPARNIK_URL", "http://127.0.0.1:3000").rstrip("/")
EMAIL = os.environ.get("NAPARNIK_EMAIL", "")
PASSWORD = os.environ.get("NAPARNIK_PASSWORD", "")
BASE_MODEL = os.environ.get("NAPARNIK_BASE_MODEL", "gemini-3.5-flash-lite")
TTS_KEY = os.environ.get("TTS_API_KEY", "naparnik-tts-local")
TTS_VOICE = os.environ.get("TTS_VOICE", "en-US-AriaNeural")
VERIFY_TLS = os.environ.get("VERIFY_TLS", "true").lower() != "false"

DEFAULT_PRESET = "naparnik-tutor"

TUTOR_PROMPT = """You are my personal English tutor in a live spoken conversation.

Rules:
1. Always answer in English, in a natural spoken style, three sentences maximum.
2. First react to what I actually said, so the conversation keeps flowing.
3. If I made a grammar, vocabulary or word order mistake, add at the very end of the English part one short line: "Better: <the corrected sentence>". Give only the single most important correction, never a list of errors.
4. Your answer is read aloud by a speech synthesiser, so no markdown, no bullet points, no emoji, no brackets, no stage directions.
5. End with one short question that keeps me talking.
6. If I ask you to explain something in Russian or to switch language, do it briefly, then return to English.
7. After the English part, on a new line, write exactly the marker [[ru]] and then start the Russian block with the word "Перевод:" followed by a short natural Russian translation of everything above. Translate the correction too and put it in Russian: "Лучше: <перевод исправленного предложения>". Two or three short Russian lines. This part is for reading only and is never spoken aloud. The Russian block must contain no English words except the labels. Example of the exact required format:

I see, that happens to everyone. What did you do next?
Better: Yesterday I went to the shop and bought bread.
[[ru]]
Перевод: Понимаю, такое бывает со всеми. Что ты сделал потом?
Лучше: Вчера я сходил в магазин и купил хлеб."""

DRILL_PROMPT = """You are my English drill coach. No small talk, no role-play.

Work in rounds:
1. Give exactly five short exercises on one topic I name, or a mixed B1 set if I do not name one. Number them 1-5.
2. Wait for my answers. I may answer in any order or skip some.
3. Check every answer: "1) OK" or "1) NO — correct: <right version> (<one-line rule>)".
4. Then give the next round of five: if I made two or more mistakes, make it easier; if everything was right, make it harder.

Exercise types: translate from Russian into English, gap-fill, fix the mistake, make a question, put the words in the right order.
Keep sentences short (up to 12 words) and useful in everyday life.
English for exercises, Russian allowed in the one-line rule explanations.
No emoji, no markdown tables, no long explanations.
If I write "стоп" or "stop", stop and summarise my three weakest spots in three bullets."""

LEVEL_PROMPT = """You are an English placement examiner. Determine my CEFR level (A2, B1, B2 or C1) in one session and explain the result.

Run a structured test, one task at a time, waiting for my answer before the next:
1. Grammar: four tasks (choose the correct form, rewrite in the past, make a question, fix the mistake).
2. Vocabulary: three tasks (say it in English, choose the right word, explain the difference in one line).
3. Speaking: three questions that need two or three sentence answers (work, past experience, future plans).
4. Comprehension: two short sentences with a question about each.

Do not correct me during the test. Do not show scores per task.
After the last task, output exactly this structure:
- Уровень: A2, B1, B2 или C1
- Почему: three bullet points with evidence (what I handled, what I did not)
- Три слабых места
- Что тренировать в первую очередь

Rules: tasks in English, final summary in Russian, no hints, no extra tasks."""

PRESETS = [
    {
        "id": "naparnik-tutor",
        "name": "Напарник — English tutor",
        "description": "Разговорный тьютор: ответ по-английски, одна коррекция, ниже перевод на русский.",
        "system": TUTOR_PROMPT,
        "temperature": 0.7,
    },
    {
        "id": "naparnik-drill",
        "name": "Напарник — тренажёр",
        "description": "Упражнения по 5 штук с проверкой: перевод, пропуски, исправление ошибок, вопросы, порядок слов.",
        "system": DRILL_PROMPT,
        "temperature": 0.5,
    },
    {
        "id": "naparnik-level",
        "name": "Напарник — проверка уровня",
        "description": "Структурированный тест на 12 заданий: определяет CEFR-уровень и слабые места.",
        "system": LEVEL_PROMPT,
        "temperature": 0.4,
    },
]

SSL_CTX = None if VERIFY_TLS else ssl._create_unverified_context()


def call(path, data=None, token=None):
    req = urllib.request.Request(URL + path, method="POST" if data is not None else "GET")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    try:
        with urllib.request.urlopen(req, body, timeout=120, context=SSL_CTX) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw.strip().startswith((b"{", b"[")) else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:300]


def upsert_preset(preset):
    model = {
        "id": preset["id"],
        "base_model_id": BASE_MODEL,
        "name": preset["name"],
        "meta": {"description": preset["description"]},
        "params": {
            "system": preset["system"],
            "temperature": preset["temperature"],
            "max_tokens": 4000,
        },
        "is_active": True,
    }
    return model


def main():
    if not EMAIL or not PASSWORD:
        sys.exit("нужны NAPARNIK_EMAIL и NAPARNIK_PASSWORD")

    st, resp = call("/api/v1/auths/signin", {"email": EMAIL, "password": PASSWORD})
    if st != 200:
        sys.exit(f"вход не удался: {st} {resp}")
    token = resp["token"]
    print(f"вход: ok ({EMAIL}, роль {resp.get('role')})")

    for preset in PRESETS:
        model = upsert_preset(preset)
        st, _ = call("/api/v1/models/create", model, token=token)
        if st != 200:
            st, _ = call("/api/v1/models/model/update", model, token=token)
        print(f"пресет {preset['id']}: {'ok' if st == 200 else f'ошибка {st}'}")

    st, cfg = call("/api/v1/audio/config", token=token)
    if st != 200:
        sys.exit(f"не прочитал настройки аудио: {st}")
    cfg["stt"]["ENGINE"] = ""
    cfg["stt"]["WHISPER_MODEL"] = cfg["stt"].get("WHISPER_MODEL") or "base"
    cfg["tts"]["ENGINE"] = "openai"
    cfg["tts"]["OPENAI_API_BASE_URL"] = "http://naparnik-tts:4000/v1"
    cfg["tts"]["OPENAI_API_KEY"] = TTS_KEY
    cfg["tts"]["MODEL"] = "tts-1"
    cfg["tts"]["VOICE"] = TTS_VOICE
    cfg["tts"]["SPLIT_ON"] = "none"
    st, resp = call("/api/v1/audio/config/update", {"tts": cfg["tts"], "stt": cfg["stt"]}, token=token)
    if st != 200:
        sys.exit(f"не удалось сохранить настройки аудио: {st} {resp}")
    print(f"аудио: STT локальный Whisper, TTS {TTS_VOICE}, нарезка выключена")

    st, models_cfg = call("/api/v1/configs/models", token=token)
    if st == 200:
        models_cfg["DEFAULT_MODELS"] = DEFAULT_PRESET
        st, _ = call("/api/v1/configs/models", models_cfg, token=token)
        print("модель по умолчанию:", DEFAULT_PRESET if st == 200 else f"ошибка {st}")

    print("\nготово. Откройте приложение, включите Настройки → Аудио → Auto-Playback Response.")


if __name__ == "__main__":
    main()
