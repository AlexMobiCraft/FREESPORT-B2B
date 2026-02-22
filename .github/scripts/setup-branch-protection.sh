#!/bin/bash

# Скрипт для настройки правил защиты веток в GitHub репозитории
# Использование: ./setup-branch-protection.sh [repo_owner] [repo_name] [github_token]

set -e

# Параметры по умолчанию
REPO_OWNER=${1:-$(echo "$GITHUB_REPOSITORY" | cut -d'/' -f1)}
REPO_NAME=${2:-$(echo "$GITHUB_REPOSITORY" | cut -d'/' -f2)}
GITHUB_TOKEN=${3:-$GITHUB_TOKEN}

if [[ -z "$GITHUB_TOKEN" ]]; then
    echo "❌ Требуется GitHub токен"
    echo "Использование: $0 [repo_owner] [repo_name] [github_token]"
    exit 1
fi

API_URL="https://api.github.com"

echo "🔧 Настройка правил защиты веток для репозитория $REPO_OWNER/$REPO_NAME"

# Функция для создания правила защиты ветки
create_branch_protection() {
    local branch=$1
    local description=$2
    
    echo "📋 Настройка правил для ветки: $branch ($description)"
    
    # Проверяем существование ветки
    if ! gh api --silent "repos/$REPO_OWNER/$REPO_NAME/branches/$branch"; then
        echo "⚠️ Ветка $branch не существует, пропускаем настройку"
        return 0
    fi
    
    # Создаем правило защиты ветки
    response=$(gh api --method PUT \
        "repos/$REPO_OWNER/$REPO_NAME/branches/$branch/protection" \
        --field required_status_checks='{
            "strict": true,
            "contexts": [
                "Backend CI/CD (test)",
                "Frontend CI/CD (test)",
                "Django CI (build)"
            ]
        }' \
        --field enforce_admins=true \
        --field required_pull_request_reviews='{
            "required_approving_review_count": 1,
            "dismiss_stale_reviews": true,
            "require_code_owner_reviews": false,
            "require_last_push_approval": true,
            "bypass_pull_request_allowances": {
                "users": [],
                "teams": []
            }
        }' \
        --field restrictions=null \
        --field allow_force_pushes=false \
        --field allow_deletions=false \
        --field block_creations=false \
        --field required_conversation_resolution=true \
        --field lock_branch=false \
        --field allow_fork_syncing=false \
        --field required_linear_history=false 2>/dev/null || echo "FAILED")
    
    if [[ "$response" == "FAILED" ]]; then
        echo "⚠️ Не удалось обновить правила для ветки $branch (возможно, они уже существуют)"
        
        # Пытаемся обновить существующие правила
        echo "🔄 Попытка обновления существующих правил..."
        response=$(gh api --method PATCH \
            "repos/$REPO_OWNER/$REPO_NAME/branches/$branch/protection" \
            --field required_status_checks='{
                "strict": true,
                "contexts": [
                    "Backend CI/CD (test)",
                    "Frontend CI/CD (test)",
                    "Django CI (build)"
                ]
            }' \
            --field enforce_admins=true \
            --field required_pull_request_reviews='{
                "required_approving_review_count": 1,
                "dismiss_stale_reviews": true,
                "require_code_owner_reviews": false,
                "require_last_push_approval": true,
                "bypass_pull_request_allowances": {
                    "users": [],
                    "teams": []
                }
            }' \
            --field restrictions=null \
            --field allow_force_pushes=false \
            --field allow_deletions=false \
            --field block_creations=false \
            --field required_conversation_resolution=true \
            --field lock_branch=false \
            --field allow_fork_syncing=false \
            --field required_linear_history=false 2>/dev/null || echo "FAILED")
        
        if [[ "$response" == "FAILED" ]]; then
            echo "❌ Не удалось обновить правила для ветки $branch"
            return 1
        else
            echo "✅ Правила для ветки $branch успешно обновлены"
        fi
    else
        echo "✅ Правила для ветки $branch успешно созданы"
    fi
    
    return 0
}

# Создаем правила для основной ветки (main)
create_branch_protection "main" "Основная ветка для продакшена"

# Создаем правила для ветки разработки (develop)
create_branch_protection "develop" "Ветка для разработки и тестирования"

echo ""
echo "📊 Текущие правила защиты веток:"

# Выводим текущие правила для всех защищенных веток
branches=("main" "develop")
for branch in "${branches[@]}"; do
    echo ""
    echo "🔒 Ветка: $branch"
    
    if protection=$(gh api "repos/$REPO_OWNER/$REPO_NAME/branches/$branch/protection" 2>/dev/null); then
        echo "  ✅ Ветка защищена"
        
        # Проверяем требуемые проверки статуса
        required_checks=$(echo "$protection" | jq -r '.required_status_checks.contexts[]?' 2>/dev/null || echo "Нет данных")
        if [[ -n "$required_checks" ]]; then
            echo "  📋 Требуемые проверки:"
            echo "$required_checks" | while read -r check; do
                echo "    - $check"
            done
        fi
        
        # Проверяем требуемые ревью
        if reviews=$(echo "$protection" | jq -r '.required_pull_request_reviews.required_approving_review_count' 2>/dev/null); then
            echo "  👥 Требуемые одобрения: $reviews"
        fi
        
        # Проверяем другие настройки
        strict=$(echo "$protection" | jq -r '.required_status_checks.strict' 2>/dev/null)
        echo "  🔄 Строгий статус: $strict"
        
        enforce_admins=$(echo "$protection" | jq -r '.enforce_admins.enabled' 2>/dev/null)
        echo "  👑 Применять к админам: $enforce_admins"
        
        dismiss_stale=$(echo "$protection" | jq -r '.required_pull_request_reviews.dismiss_stale_reviews' 2>/dev/null)
        echo "  🗑️ Отклонять устаревшие: $dismiss_stale"
        
    else
        echo "  ❌ Ветка не защищена или не существует"
    fi
done

echo ""
echo "🎉 Настройка правил защиты веток завершена!"
echo ""
echo "📝 Рекомендации:"
echo "1. Регулярно проверяйте актуальность требуемых проверок статуса"
echo "2. Рассмотрите возможность добавления дополнительных проверок для критических изменений"
echo "3. Настройте уведомления об изменениях в защищенных ветках"
echo "4. Периодически проверяйте права доступа к репозиторию"