# Сквозной пример: один голосовой ход

Документ фиксирует реальный прогон на этой VM 22.11.2026: синтезированная речь
с ошибкой → Whisper → пресет тьютора → ответ. Все цифры — измерения, не оценки.

Условия замера: Kali в VirtualBox, 6 vCPU (Xeon E5-2680 v4), 8 ГБ RAM, без GPU;
faster-whisper `base`, `int8`, VAD включён; модель `gemini-3.5-flash-lite`
через шлюз `opencode.ai/zen`.

## 1. Что видит пользователь

1. Открыть `https://&lt;SITE_ADDRESS&gt;` (сертификат Caddy уже в доверенных, логин помнит).
2. Модель «Напарник — English tutor» выбрана по умолчанию.
3. Нажать значок голоса и сказать фразу.
4. Через ~5–6 секунд увидеть текст и услышать ответ.

```
Ты:    Yesterday I go to the shop and buy bread.
Оно:   That is a very useful thing to do. Did you get anything else while you were there?
       Better: Yesterday I went to the shop and bought bread.
       [[ru]]
       Перевод: Это очень полезное дело. Ты купил что-нибудь еще, пока был там?
       Лучше: Вчера я сходил в магазин и купил хлеб.
```

## 2. Техническая трасса

| Шаг | Что происходит | Время |
|---|---|---|
| 1 | `POST /api/v1/auths/signin` → JWT, дальше запросы с ним | 0.42 с |
| 2 | Браузер пишет WebM/Opus и отправляет `POST /api/v1/audio/transcriptions`; Caddy принимает TLS на `:443` и проксирует в Open WebUI `:8080` | — |
| 3 | ffmpeg конвертирует в mp3, faster-whisper `base` расшифровывает | **4.41 с** (аудио 2.6 с) |
| 4 | Транскрипт → пресет `naparnik-tutor` → `opencode.ai/zen/v1` → `gemini-3.5-flash-lite` с системным промптом | **1.25 с** |
| 5 | Ответ уходит в браузер, браузер озвучивает своим английским голосом (серверного TTS нет) | ~0 с |

Итого ход: **≈ 6 с**, из них 2.6 с — длительность самой фразы.
«Добавка» системы ≈ 3.5 с.

## 3. Фактический вывод прогона

```
[1] вход:        200 (0.42с)
[2] аудио:       2.6 с речи
[3] Whisper:     200 (4.41с) → «Yesterday I go to the shop and buy bread.»
[4] Тьютор:      200 (1.25с)
--- ответ ---
That sounds like a normal errand to run. Fresh bread is always nice to have at home.
Did you buy anything else while you were there?
Better: Yesterday I went to the shop and bought bread.
```

Две детали, подтверждающие, что работает именно задуманное:

- Whisper распознал фразу **с ошибкой как есть** — он не правит грамматику,
  значит исправление даёт тьютор, а не распознавание;
- в ответе есть живая реакция, встречный вопрос и **ровно одна** коррекция
  в конце строкой `Better: ...`, как требует промпт.

## 4. Прогнать самому

### Через браузер

Открыть `https://&lt;SITE_ADDRESS&gt;`, войти (логин/пароль в `.credentials`),
нажать голосовой режим, сказать что-нибудь с ошибкой.

### Через API

Логин и пароль взять из `.credentials`.

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:3000/api/v1/auths/signin \
  -H "Content-Type: application/json" \
  -d '{"email":"<email>","password":"<password>"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

# распознавание
curl -s -X POST http://127.0.0.1:3000/api/v1/audio/transcriptions \
  -H "Authorization: Bearer $TOKEN" \
  -F "language=en" -F "file=@turn.wav;type=audio/wav"

# ответ тьютора
curl -s -X POST http://127.0.0.1:3000/api/chat/completions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"model":"naparnik-tutor","messages":[{"role":"user","content":"Yesterday I go to the shop and buy bread."}]}'
```

Ожидаемо: в первом ответе `{"text": "..."}`, во втором — `choices[0].message.content`
с реакцией, вопросом и строкой `Better:`.

### Референсные замеры STT (тот же сервер)

| Модель | Речь 2.6 с | Комментарий |
|---|---|---|
| `tiny` | 2.5 с | быстрее на копейки, текст заметно хуже |
| **`base`** | **2.7 с** | выбран |
| `small` | 7.8 с | точнее, но втрое медленнее |

Тишина 5 с при включённом VAD — 1.0 с. Без VAD то же аудио может занять 30–60 с
(модель прогоняет полное окно вхолостую).

## 5. Если что-то не так

| Симптом | Причина | Что смотреть |
|---|---|---|
| «Transcription failed» | падение STT, например неверный `audio.stt.engine` в БД | `docker logs naparnik-webui`, Admin → Settings → Audio |
| Whisper думает 30–60 с | тишина без VAD | `WHISPER_VAD_FILTER=true` в compose |
| Ответ есть, звука нет | браузерный TTS или выбран русский голос | Настройки → Audio → Text-to-speech voice |
| Предупреждение о сертификате | не установлен корневой CA Caddy | `https://&lt;SITE_ADDRESS&gt;/caddy-root.crt` |
| `401` после долгой паузы | истёк JWT | перелогиниться |
| Микрофон не активируется | не защищённый контекст | открывать `https://`, а не `http://…:3000` |

## 6. Где что лежит

| Файл | Что |
|---|---|
| `docker-compose.yml` | Open WebUI + Caddy, порты, тома |
| `Caddyfile` | HTTPS, `tls internal`, `default_sni`, выдача корневого сертификата |
| `.env` | ключ шлюза, секрет сессий, модель по умолчанию |
| `.credentials` | логин/пароль админа Open WebUI |
| `README.md` | обзор, установка сертификата, известные грабли |
