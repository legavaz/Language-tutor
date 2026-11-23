# Напарник — голосовой тьютор английского

Self-hosted разговорный тренажёр английского для дома: говоришь в микрофон —
получаешь ответ, одну исправленную ошибку и короткий перевод на русский; ответ
озвучивается нейронным голосом. Крутится в Docker на домашнем сервере, вход по
HTTPS с любого устройства в сети.

Собран на Open WebUI, без проприетарных сервисов: распознавание — локальный
Whisper, модель — любой OpenAI-совместимый шлюз, синтез — Microsoft Edge TTS.

## Что умеет

| Возможность | Как сделано |
|---|---|
| Разговор по-английски | пресет модели с промптом тьютора |
| Одна коррекция за реплику | строка `Better: …` в ответе |
| Перевод на русский | блок после маркера `[[ru]]`, **не** озвучивается |
| Озвучка ответов | `naparnik-tts`, нейронные голоса Edge |
| Распознавание речи | локальный `faster-whisper` (base, int8, VAD) |
| Оценка произношения | отдельный сервис + страница `/pron/` |
| HTTPS без публичного домена | Caddy с внутренним CA |
| Проверка микрофона | страница `/mictest.html` |

## Как это устроено

```
браузер ──HTTPS:443──▶ Caddy ──┬── /            ▶ Open WebUI ──▶ шлюз моделей
                               │                      │
                               │                      ├── STT: faster-whisper (локально)
                               │                      └── TTS: naparnik-tts ──▶ Edge TTS
                               └── /pron/*     ▶ naparnik-pron (Whisper + оценка)
```

| Контейнер | Роль |
|---|---|
| `naparnik-caddy` | HTTPS, редирект с 80, прокси на WebUI и pron |
| `naparnik-webui` | Open WebUI: чат, история, настройки, STT/TTS |
| `naparnik-tts` | OpenAI-совместимый `/v1/audio/speech` на голосах Edge |
| `naparnik-pron` | оценка произношения, страница `/pron/` |

## Требования

- Docker + Compose v2, Linux-хост (проверено на Kali в VirtualBox);
- 6+ ГБ RAM (Whisper `base` и модели в памяти) и ~10 ГБ диска;
- OpenAI-совместимый шлюз: ключ и base URL. Подойдёт opencode.ai/zen, DeepSeek, OpenAI, локальная Ollama;
- доступ к интернету: синтез речи идёт в сервис Microsoft.

## Быстрый старт

```bash
git clone <ваш-репозиторий> naparnik
cd naparnik

cp .env.example .env
# заполните OPENAI_API_BASE_URL, OPENAI_API_KEY и SITE_ADDRESS
# WEBUI_SECRET_KEY сгенерируйте: openssl rand -hex 32

docker compose up -d --build
```

Дальше:

1. Откройте `https://<SITE_ADDRESS>` и создайте первого пользователя — он станет админом.
2. Скачайте и установите корневой сертификат: `https://<SITE_ADDRESS>/caddy-root.crt`
   (Windows: двойной клик → «Локальный компьютер» → «Доверенные корневые центры»).
3. Создайте пресет тьютора и настройте звук:

   ```bash
   NAPARNIK_URL=https://<SITE_ADDRESS> \
   NAPARNIK_EMAIL=admin@example.com \
   NAPARNIK_PASSWORD='ваш-пароль' \
   python3 scripts/setup-preset.py
   ```

   Скрипт создаёт модель «Напарник — English tutor» с промптом, включает серверный
   TTS и делает пресет моделью по умолчанию.

## Использование

1. Настройки → **Аудио** → включить **Auto-Playback Response** (иначе ответы не звучат).
   Там же рядом — «Instant auto-send after voice transcription», удобно для разговора.
2. Говорить **кнопкой микрофона в поле ввода**, а не через «Voice mode»: в режиме
   звонка переписка не отображается.
3. Модель в поле ввода — «Напарник — English tutor».

Пример хода:

```
Ты:    Yesterday I go to the shop and buy bread.
Оно:   Fresh bread is always great to have at home. Did you eat it right away?
       Better: Yesterday I went to the shop and bought bread.
       [[ru]]
       Перевод: Свежий хлеб всегда приятно иметь дома. Ты съел его сразу?
       Лучше: Вчера я сходил в магазин и купил хлеб.
```

Замеры на 6 vCPU без GPU: распознавание 2.6-секундной фразы ≈ 2.7 с, ответ модели
≈ 1 с, синтез ≈ 1.5 с. Подробный разбор одного хода — в [EXAMPLE.md](EXAMPLE.md).

## Оценка произношения

`https://<SITE_ADDRESS>/pron/` — запись до 10 секунд, затем разбор по словам
(зелёный/жёлтый/красный по уверенности), общая оценка и список слов на повтор.
Если вписать эталонную фразу — покажет, что не прозвучало.

Честное ограничение: это уверенность распознавания, а не фонемный анализ. Плохая
оценка ловит проглоченные слоги и тихую речь, но не скажет «ты произносишь θ как s».

## Настройки

| Переменная | Назначение |
|---|---|
| `OPENAI_API_BASE_URL`, `OPENAI_API_KEY` | шлюз моделей |
| `WEBUI_SECRET_KEY` | секрет сессий, `openssl rand -hex 32` |
| `DEFAULT_MODEL` | id пресета по умолчанию |
| `SITE_ADDRESS` | IP или DNS-имя хоста (для сертификата и SNI) |
| `WEBUI_PUBLIC_URL` | публичный адрес для ссылок в интерфейсе |
| `WEBUI_HTTP_PORT` | прямой HTTP-порт (резервный вход) |
| `TTS_API_KEY` | внутренний ключ WebUI ↔ naparnik-tts |
| `TTS_VOICE` | голос: `en-US-AriaNeural`, `en-US-JennyNeural`, `en-US-GuyNeural`, `en-GB-SoniaNeural`, `en-GB-RyanNeural` |

Порт 3000 открыт в LAN как резерв. Если он не нужен, замените в compose на
`"127.0.0.1:${WEBUI_HTTP_PORT:-3000}:8080"`.

## Грабли, на которые уже наступили

Все проверены на Open WebUI 0.13.4 — если что-то сломается после обновления,
начинайте отсюда.

- **Настройки аудио живут в базе**, переменные окружения задают только умолчания
  при первой инициализации. Если в базе остался неверный движок (например
  `whisper` или `edge-tts`), распознавание падает с `'NoneType' object is not
  subscriptable`. Лечится в Admin → Settings → Audio.
- **Локальный Whisper включается пустой строкой** движка, значения `whisper` в
  коде нет.
- **Без `WHISPER_VAD_FILTER=true`** Whisper на тишине может работать 30–60 секунд.
- **`split_on = punctuation`** режет ответ на куски, и русский блок уходит в
  синтез отдельным запросом без маркера. Поэтому `none`.
- **Роль `user` не видит модели без явного гранта** доступа — включён
  `BYPASS_MODEL_ACCESS_CONTROL`.
- **Готовый образ `travisvn/openai-edge-tts` содержит edge-tts 7.2.7**, которую
  Microsoft уже не пускает (403). Лечится обновлением до 7.3.1 в `tts.Dockerfile`.
- **`default_sni` в Caddyfile обязателен**: по IP клиенты не передают SNI, иначе
  `TLS alert internal error`.
- **Тег `:main` Open WebUI меняется молча**, поэтому образ запинен по digest.

## Безопасность

- `.env` и сертификаты в `.gitignore`; в репозитории только `.env.example`.
- Проверка перед коммитом: `scripts/check-secrets.sh`.
- Корневой CA Caddy — локальный: ставится в доверенные только на ваших устройствах.
  Приватного ключа от публичного домена здесь нет.
- Все сервисы, кроме Caddy, доступны только внутри docker-сети; наружу открыты
  80/443 и резервный HTTP-порт.

## Структура

```
docker-compose.yml     стек: webui, tts, pron, caddy
Caddyfile              HTTPS, внутренний CA, /pron/
.env.example           шаблон конфигурации
pron/                  сервис оценки произношения (FastAPI + faster-whisper)
tts.Dockerfile         сборка озвучки (edge-tts 7.3.1)
tts-patch.py           патч: отрезать русский блок, подменить голос, заглушка
silence.b64            тишина для пустых фрагментов
pron.Dockerfile        сборка сервиса произношения
mictest.html           страница проверки микрофона
scripts/setup-preset.py  создание пресета и настройка звука
scripts/check-secrets.sh проверка на утечки перед коммитом
EXAMPLE.md             разбор одного голосового хода с замерами
```

## Лицензия

MIT, см. [LICENSE](LICENSE). Используемые образы и модели — под своими лицензиями
(Open WebUI, Caddy, edge-tts, faster-whisper, gemini/deepseek и т. д.).
