"""Сервис оценки произношения «Напарника».

Принимает запись, распознаёт её с пофразовыми вероятностями и отдаёт:
  * текст, что услышала модель;
  * уверенность по каждому слову (0..1);
  * сводную оценку и список «трудных» слов;
  * если передана эталонная фраза — чего не хватило и что лишнее.

Честная оговорка: это не фонемный анализ. Оценка показывает, насколько
уверенно распознаватель разобрал слово. Плохая уверенность почти всегда
означает проблему с произношением, шум или слишком тихую запись, но причину
сервис не различает.
"""

import asyncio
import os
import subprocess
import tempfile

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

MODEL_DIR = os.environ.get("WHISPER_MODEL_DIR", "/data/cache/whisper/models")
MODEL_NAME = os.environ.get("WHISPER_MODEL", "base")
WEAK_THRESHOLD = float(os.environ.get("WEAK_THRESHOLD", "0.55"))

_model = None
_lock = asyncio.Lock()

app = FastAPI(title="naparnik-pron")
HERE = os.path.dirname(os.path.abspath(__file__))


def get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8", download_root=MODEL_DIR)
    return _model


def to_wav16k(src: str) -> str:
    dst = src + ".16k.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ar", "16000", "-ac", "1", dst],
        check=True,
    )
    return dst


def normalize(word: str) -> str:
    return "".join(ch for ch in word.lower() if ch.isalnum() or ch == "'")


@app.get("/health")
def health():
    return {"ok": True, "model": MODEL_NAME}


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
        return f.read()


@app.post("/score")
async def score(file: UploadFile = File(...), target: str = Form("")):
    raw = await file.read()
    if not raw:
        return JSONResponse({"error": "пустая запись"}, status_code=400)

    suffix = os.path.splitext(file.filename or "rec.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(raw)
        src = f.name

    wav = None
    try:
        wav = await asyncio.to_thread(to_wav16k, src)

        def run():
            model = get_model()
            segments, info = model.transcribe(
                wav, beam_size=5, vad_filter=True, language="en", word_timestamps=True
            )
            words = []
            for seg in segments:
                for w in seg.words or []:
                    token = w.word.strip()
                    if token:
                        words.append({"word": token, "prob": round(float(w.probability), 3), "start": round(float(w.start), 2)})
            return words

        async with _lock:
            words = await asyncio.to_thread(run)

        if not words:
            return JSONResponse(
                {"error": "речь не распознана: тишина, слишком тихо или не английский", "words": [], "overall": 0.0},
                status_code=200,
            )

        probs = [w["prob"] for w in words]
        overall = round(sum(probs) / len(probs), 3)
        weak = [w for w in words if w["prob"] < WEAK_THRESHOLD]
        heard = " ".join(w["word"] for w in words)

        result = {
            "heard": heard,
            "words": words,
            "overall": overall,
            "weak": weak,
            "target": (target or "").strip(),
        }

        if result["target"]:
            import difflib

            want = [t for t in (normalize(x) for x in result["target"].split()) if t]
            got = [t for t in (normalize(x) for x in heard.split()) if t]
            sm = difflib.SequenceMatcher(a=want, b=got)
            missing, extra = [], []
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag in ("delete", "replace"):
                    missing += want[i1:i2]
                if tag in ("insert", "replace"):
                    extra += got[j1:j2]
            result["missing"] = missing
            result["extra"] = extra

        return result
    finally:
        for p in (src, wav):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass
