#!/bin/bash

# Настройка правил защиты веток в GitHub репозитории.
#
# Использование:
#   MODE=check ./setup-branch-protection.sh [repo_owner] [repo_name] [github_token]
#   MODE=apply ./setup-branch-protection.sh [repo_owner] [repo_name] [github_token]
#
# MODE=check (по умолчанию) — только читает и печатает текущее состояние, ничего не меняет.
# MODE=apply               — применяет правила; перед этим проверяет, что все требуемые
#                            контексты реально существуют (см. preflight ниже).
#
# ⚠️ ПЕРЕД ПРИМЕНЕНИЕМ ПРОЧИТАЙ (проверено 2026-09-07 через gh api):
#
# 0. Скрипту нужен PAT с правами администратора репозитория (в CI — секрет
#    BRANCH_PROTECTION_TOKEN). GITHUB_TOKEN не подходит: и чтение, и запись branch
#    protection требуют admin, а области `administration` в блоке `permissions`
#    workflow не существует.
# 1. Ни main, ни develop сейчас НЕ защищены — оба отдают «Branch not protected».
#    Этот скрипт ни разу не применился успешно; всё, что ниже, — намерение, а не
#    текущее состояние.
# 2. GitHub именует check-run по имени джобы (плюс значения матрицы), а не
#    «workflow (job)»: чек Django CI называется `build (3.12)`. Прежний список
#    контекстов был выдуман и не совпадал ни с одним реальным чеком; исправлено
#    2026-09-07 вместе с двумя причинами, из-за которых совпасть было нельзя:
#    джобы backend-ci и frontend-ci обе назывались `test` (теперь у них явные
#    разные `name`), а paths-фильтры не давали чекам появиться на части PR
#    (сняты у pull_request). MODE=apply всё равно гоняет preflight и отказывается
#    применять правила, если хоть один контекст не найден среди реальных чеков
#    ветки: иначе PR встанет на «Expected — waiting for status» навсегда.
#    E2E Tests в список намеренно не включён — он красный с 2026-09-05.
# 3. В репозитории один коллаборатор (проверено 2026-09-07). Поэтому
#    required_approving_review_count = 0, а require_last_push_approval = false:
#    свой PR апрувить нельзя, и любое ненулевое требование ревью вместе с
#    enforce_admins = true намертво блокирует мерж, снять который можно только
#    сняв защиту. PR при этом всё равно обязателен — прямой push в main/develop
#    запрещён, и обязательные проверки статуса действуют. Как только появится
#    второй мейнтейнер, оба значения имеет смысл вернуть к 1 и true.
# 3a. strict = false и required_conversation_resolution = false — сознательный выбор
#    для репозитория с одним мейнтейнером (2026-09-07). strict потребовал бы
#    подтягивать develop в каждую ветку перед мержем, а resolution блокировал бы мерж
#    из-за незакрытого треда бота claude-review. Запрет прямого push и пять
#    обязательных проверок — то, ради чего защита включается, — сохранены.
# 4. Ни у одного workflow из REQUIRED_CONTEXTS больше нет paths-фильтра на
#    pull_request — это условие обязательно и его нельзя вернуть, не сломав мерж.
#    Добавляя контекст в список, проверь, что его workflow срабатывает на КАЖДОМ PR
#    в main/develop. Preflight этого не гарантирует: он смотрит один коммит, где
#    нужные пути могли быть затронуты.

set -euo pipefail

REPO_OWNER=${1:-$(echo "${GITHUB_REPOSITORY:-}" | cut -d'/' -f1)}
REPO_NAME=${2:-$(echo "${GITHUB_REPOSITORY:-}" | cut -d'/' -f2)}
GITHUB_TOKEN=${3:-${GITHUB_TOKEN:-}}
MODE=${MODE:-check}

export GITHUB_TOKEN

if [[ -z "$GITHUB_TOKEN" ]]; then
    echo "❌ Токен не задан."
    echo "   Нужен PAT с правами администратора репозитория: classic со scope 'repo'"
    echo "   либо fine-grained с разрешением «Administration: Read and write»."
    echo "   В CI он приходит из секрета BRANCH_PROTECTION_TOKEN; штатный GITHUB_TOKEN"
    echo "   не подходит — область administration в блоке permissions недоступна."
    echo "Использование: MODE=check|apply $0 [repo_owner] [repo_name] [github_token]"
    exit 1
fi

if [[ -z "$REPO_OWNER" || -z "$REPO_NAME" ]]; then
    echo "❌ Не определён репозиторий: передай owner и name аргументами или задай GITHUB_REPOSITORY"
    exit 1
fi

if [[ "$MODE" != "check" && "$MODE" != "apply" ]]; then
    echo "❌ MODE должен быть 'check' или 'apply', получено: '$MODE'"
    exit 1
fi

# На ubuntu-latest оба предустановлены, но проверка дешевле, чем разбор невнятного падения.
for tool in gh jq; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "❌ Не найден $tool — он обязателен для работы скрипта"
        exit 1
    fi
done

BRANCHES=("main" "develop")

# Контексты, которые станут обязательными. Менять только вместе с preflight-проверкой —
# см. предупреждение в шапке.
REQUIRED_CONTEXTS=(
    "Бэкенд: тесты"
    "Фронтенд: тесты"
    "build (3.12)"
    "Контракт синхронен с кодом"
    "Проверки качества кода"
)

FAILED=0

echo "🔧 Репозиторий: $REPO_OWNER/$REPO_NAME"
echo "🔧 Режим: $MODE"
echo ""

# Собирает JSON тела запроса. Контексты подставляются через jq, а не склейкой строк:
# имена содержат пробелы, скобки и кириллицу.
#
# Раньше тело собиралось через `gh api --field required_status_checks='{...}'`. Это
# ошибка: --field передаёт значение строкой, объектом оно не становится, и API отвечает
# 422. Правильный способ — отдать готовый JSON через --input -.
protection_payload() {
    printf '%s\n' "${REQUIRED_CONTEXTS[@]}" | jq -R . | jq -s '{
        required_status_checks: {
            strict: false,
            contexts: .
        },
        enforce_admins: true,
        required_pull_request_reviews: {
            required_approving_review_count: 0,
            dismiss_stale_reviews: true,
            require_code_owner_reviews: false,
            require_last_push_approval: false
        },
        restrictions: null,
        allow_force_pushes: false,
        allow_deletions: false,
        block_creations: false,
        required_conversation_resolution: false,
        lock_branch: false,
        allow_fork_syncing: false,
        required_linear_history: false
    }'
}

# Собирает имена чеков (check-run от Actions и commit status от внешних сервисов),
# сообщённые на указанном коммите.
reported_checks_for() {
    local sha=$1
    {
        gh api --paginate "repos/$REPO_OWNER/$REPO_NAME/commits/$sha/check-runs"             --jq '.check_runs[].name' 2>/dev/null || true
        gh api "repos/$REPO_OWNER/$REPO_NAME/commits/$sha/status"             --jq '.statuses[].context' 2>/dev/null || true
    } | sort -u
}

# Проверяет, что каждый требуемый контекст реально где-то сообщался.
# Без этого применение правил вешает все будущие PR на «Expected — waiting for status».
#
# Смотрим ДВА коммита, и это не перестраховка. Required-контексты оцениваются на head
# коммите PR, а часть workflow срабатывает только на одном из событий: pre-merge-checks
# запускается исключительно на `pull_request`, поэтому на HEAD ветки (push-событие) его
# чека нет вовсе; наоборот, у backend-ci и frontend-ci `paths`-фильтр остался на push,
# так что на конкретном PR-коммите они есть, а на некоторых push-коммитах — нет.
# Объединение покрывает оба случая.
preflight_contexts() {
    local branch=$1
    local head_sha pr_sha reported missing=0 sources=""

    if ! head_sha=$(gh api "repos/$REPO_OWNER/$REPO_NAME/commits/$branch" --jq '.sha' 2>&1); then
        echo "  ❌ Не удалось получить HEAD ветки $branch:"
        echo "$head_sha" | sed 's/^/    /'
        return 1
    fi
    sources="HEAD ${head_sha:0:8}"

    # Head последнего PR в эту ветку — именно там появляются чеки, привязанные к
    # событию pull_request.
    pr_sha=$(gh api "repos/$REPO_OWNER/$REPO_NAME/pulls?base=$branch&state=all&sort=updated&direction=desc&per_page=1"         --jq '.[0].head.sha' 2>/dev/null || true)
    if [[ -n "$pr_sha" && "$pr_sha" != "null" && "$pr_sha" != "$head_sha" ]]; then
        sources="$sources + PR ${pr_sha:0:8}"
    else
        pr_sha=""
    fi

    reported=$(
        {
            reported_checks_for "$head_sha"
            [[ -n "$pr_sha" ]] && reported_checks_for "$pr_sha"
        } | sort -u
    )

    if [[ -z "$reported" ]]; then
        echo "  ❌ Ни на одном из коммитов ($sources) нет чеков — применять правила нельзя"
        return 1
    fi

    echo "  🔍 Preflight по: $sources"
    for ctx in "${REQUIRED_CONTEXTS[@]}"; do
        if grep -Fxq "$ctx" <<<"$reported"; then
            echo "    ✅ найден контекст: $ctx"
        else
            echo "    ❌ контекст НЕ найден: $ctx"
            missing=$((missing + 1))
        fi
    done

    if [[ $missing -gt 0 ]]; then
        echo "  ❌ Не найдено контекстов: $missing. Фактически сообщались:"
        sed 's/^/    - /' <<<"$reported"
        echo "  ⛔ Применение отменено: такие правила заблокировали бы мерж навсегда."
        return 1
    fi

    return 0
}

apply_branch_protection() {
    local branch=$1
    local description=$2
    local out

    echo "📋 Применение правил для ветки: $branch ($description)"

    if ! out=$(gh api --silent "repos/$REPO_OWNER/$REPO_NAME/branches/$branch" 2>&1); then
        echo "  ⚠️ Ветка $branch не существует или недоступна:"
        echo "$out" | sed 's/^/    /'
        return 1
    fi

    if ! preflight_contexts "$branch"; then
        return 1
    fi

    if ! out=$(protection_payload | gh api --method PUT \
        "repos/$REPO_OWNER/$REPO_NAME/branches/$branch/protection" --input - 2>&1); then
        echo "  ❌ API отклонил запрос для ветки $branch:"
        echo "$out" | sed 's/^/    /'
        return 1
    fi

    # Успех PUT ещё не гарантирует состояние — перечитываем.
    if ! out=$(gh api "repos/$REPO_OWNER/$REPO_NAME/branches/$branch/protection" 2>&1); then
        echo "  ❌ PUT прошёл, но ветка $branch по-прежнему не защищена:"
        echo "$out" | sed 's/^/    /'
        return 1
    fi

    echo "  ✅ Правила для ветки $branch применены и подтверждены чтением"
    return 0
}

report_branch_protection() {
    local branch=$1
    local protection

    echo ""
    echo "🔒 Ветка: $branch"

    if ! protection=$(gh api "repos/$REPO_OWNER/$REPO_NAME/branches/$branch/protection" 2>&1); then
        if grep -q "Branch not protected" <<<"$protection"; then
            echo "  ❌ Ветка НЕ защищена"
        else
            echo "  ❌ Не удалось прочитать правила (нужен доступ administration):"
            echo "$protection" | sed 's/^/    /'
        fi
        return 1
    fi

    echo "  ✅ Ветка защищена"
    echo "  📋 Требуемые проверки:"
    jq -r '.required_status_checks.contexts[]? // empty' <<<"$protection" | sed 's/^/    - /'
    echo "  👥 Требуемые одобрения: $(jq -r '.required_pull_request_reviews.required_approving_review_count // "нет"' <<<"$protection")"
    echo "  🔄 Строгий статус: $(jq -r '.required_status_checks.strict // "нет"' <<<"$protection")"
    echo "  👑 Применять к админам: $(jq -r '.enforce_admins.enabled // "нет"' <<<"$protection")"
    echo "  🗑️ Отклонять устаревшие: $(jq -r '.required_pull_request_reviews.dismiss_stale_reviews // "нет"' <<<"$protection")"
    return 0
}

if [[ "$MODE" == "apply" ]]; then
    apply_branch_protection "main" "Основная ветка для продакшена" || FAILED=1
    apply_branch_protection "develop" "Ветка для разработки и тестирования" || FAILED=1
    echo ""
fi

echo "📊 Текущее состояние защиты веток:"
for branch in "${BRANCHES[@]}"; do
    if ! report_branch_protection "$branch"; then
        if [[ "$MODE" == "apply" ]]; then
            FAILED=1
        fi
    fi
done

echo ""
if [[ $FAILED -ne 0 ]]; then
    echo "❌ Настройка правил защиты веток НЕ выполнена — см. ошибки выше."
    exit 1
fi

if [[ "$MODE" == "check" ]]; then
    echo "ℹ️ Режим check: ничего не изменено. Для применения запусти workflow с mode=apply."
else
    echo "🎉 Правила защиты веток применены."
fi
