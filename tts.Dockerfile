# TTS-сервис «Напарника».
#
# 1. Готовый образ travisvn/openai-edge-tts собран со старой edge-tts 7.2.7,
#    у которой просрочен TrustedClientToken — Microsoft отвечает 403 на
#    рукопожатие wss://speech.platform.bing.com. Обновление до 7.3.1 лечит.
# 2. Патч tts-patch.py вырезает из текста русский перевод (после маркера [[ru]]),
#    чтобы английский голос не читал кириллицу.
#
# Пины версий обязательны: при следующем сломе достаточно поднять номер.

FROM travisvn/openai-edge-tts@sha256:af8df8fb39719623cb6c3dbcba87ab65813030d97e20ae436d3161a53d41d72a

RUN pip install --no-cache-dir "edge-tts==7.3.1"

COPY tts-patch.py /tmp/tts-patch.py
COPY silence.b64 /tmp/silence.b64
RUN python /tmp/tts-patch.py
