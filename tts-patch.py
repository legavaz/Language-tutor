"""Патч сервиса синтеза «Напарника».

Зачем:
1. Модель выдаёт ответ в формате

       English reaction. Question?
       Better: corrected sentence.
       [[ru]]
       Перевод: ...
       Лучше: ...

   Всё после маркера [[ru]] — только для чтения глазами. Режем эту часть перед
   синтезом, чтобы английский голос не читал кириллицу.

2. Пустой текст раньше уходил в edge-tts и давал NoAudioReceived -> 500.
   Теперь это понятная ошибка 400.

3. Если в куске осталась только кириллица, английский голос её не озвучит —
   подменяем голос на русский (Svetlana; Dariya в этой сборке недоступна).

4. Если букв нет вообще (одна пунктуация), отдаём короткую тишину: ошибка
   пользователю не нужна, а говорить нечего.

Скрипт идемпотентный.
"""

import base64
import os

PATH = "/app/server.py"
MARK = "RU_MARKER"
SILENCE = "/app/silence.mp3"
SILENCE_B64 = "/tmp/silence.b64"

OLD = "        text = data.get('input')\n"

NEW = (
    "        text = data.get('input')\n"
    "        # RU_MARKER: вырезаем русский перевод перед синтезом\n"
    "        if isinstance(text, str) and '[[ru]]' in text:\n"
    "            head = text.split('[[ru]]')[0].strip()\n"
    "            text = head or text.strip()\n"
    "        if not isinstance(text, str) or not text.strip():\n"
    "            return jsonify({'error': 'empty input'}), 400\n"
    "        if not re.search(r'[A-Za-z]', text):\n"
    "            if re.search(r'[А-Яа-яЁё]', text):\n"
    "                # RU_MARKER_VOICE: кириллица -> русский голос\n"
    "                data['voice'] = 'ru-RU-SvetlanaNeural'\n"
    "            else:\n"
    "                # RU_MARKER_SILENCE: букв нет, говорить нечего\n"
    "                try:\n"
    "                    with open('/app/silence.mp3', 'rb') as _sf:\n"
    "                        return Response(_sf.read(), mimetype='audio/mpeg')\n"
    "                except OSError:\n"
    "                    return jsonify({'error': 'nothing to speak'}), 400\n"
)

src = open(PATH, encoding="utf-8").read()

if MARK in src:
    print("патч уже применён")
else:
    if OLD not in src:
        raise SystemExit("не нашёл место для патча в server.py")
    src = src.replace(OLD, NEW, 1)

    if "\nimport re\n" not in src:
        src = src.replace("\nimport os\n", "\nimport os\nimport re\n", 1)

    open(PATH, "w", encoding="utf-8").write(src)
    print("патч применён")

if os.path.exists(SILENCE_B64) and not os.path.exists(SILENCE):
    with open(SILENCE_B64) as f:
        open(SILENCE, "wb").write(base64.b64decode(f.read().strip()))
    print("тишина записана:", os.path.getsize(SILENCE), "байт")
