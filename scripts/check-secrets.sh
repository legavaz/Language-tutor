#!/usr/bin/env bash
# Проверка перед публикацией: не попали ли в индекс секреты.
#
#   ./scripts/check-secrets.sh
#
# Проверяет файлы, которые git готов отправить (staged + tracked), и падает
# с кодом 1, если находит ключи, пароли или приватные ключи.

set -uo pipefail
fail=0

say() { printf '%s\n' "$*"; }

# 1. Файлы, которых в репозитории быть не должно
forbidden=".env .credentials"
for f in $forbidden; do
    if git ls-files --cached --error-unmatch "$f" >/dev/null 2>&1; then
        say "ОШИБКА: $f попал в индекс. Уберите: git rm --cached $f"
        fail=1
    fi
done

# 2. Приватные ключи и сертификаты в индексе
if git ls-files --cached | grep -qE '\.(key|pem|p12|pfx)$'; then
    say "ОШИБКА: в индексе приватные ключи или сертификаты:"
    git ls-files --cached | grep -E '\.(key|pem|p12|pfx)$'
    fail=1
fi

# 3. Похожее на секреты в содержимом
patterns='(oc_sk_[A-Za-z0-9]{10,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[baprs]-[A-Za-z0-9-]{10,})'
hits=$(git grep -nIE "$patterns" -- . ':!.env.example' 2>/dev/null || true)
if [ -n "$hits" ]; then
    say "ОШИБКА: похоже на секреты:"
    printf '%s\n' "$hits"
    fail=1
fi

# 4. Пароль в явном виде (осторожная эвристика)
hits=$(git grep -nIE '(password|passwd|secret|api_?key)[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"'$<{]{6,}["'"'"']' -- . 2>/dev/null || true)
if [ -n "$hits" ]; then
    say "ВНИМАНИЕ: проверьте строки с паролями:"
    printf '%s\n' "$hits"
fi

if [ "$fail" -eq 0 ]; then
    say "Секретов в индексе не найдено."
else
    say ""
    say "Исправьте замечания выше и повторите."
    exit 1
fi
