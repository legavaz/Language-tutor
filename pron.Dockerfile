# РЎРµСЂРІРёСЃ РѕС†РµРЅРєРё РїСЂРѕРёР·РЅРѕС€РµРЅРёСЏ.
#
# РЎРѕР±РёСЂР°РµС‚СЃСЏ РїРѕРІРµСЂС… СѓР¶Рµ СЃРєР°С‡Р°РЅРЅРѕРіРѕ РѕР±СЂР°Р·Р° Open WebUI: С‚Р°Рј РµСЃС‚СЊ fastapi,
# uvicorn, faster-whisper Рё ffmpeg вЂ” РЅРёС‡РµРіРѕ Р»РёС€РЅРµРіРѕ С‚СЏРЅСѓС‚СЊ РЅРµ РЅСѓР¶РЅРѕ.

FROM ghcr.io/open-webui/open-webui@sha256:d6c085678f7e3f474aa2a92ac9831cb68759dcfd951de250ebbb37dac5cd0255

WORKDIR /app/pron
COPY pron/server.py pron/index.html ./

ENV WHISPER_MODEL=base \
    WHISPER_MODEL_DIR=/data/cache/whisper/models \
    WEAK_THRESHOLD=0.55

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
