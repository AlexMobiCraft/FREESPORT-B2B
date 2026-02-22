#!/usr/bin/env python
"""
Простой скрипт для ручного тестирования User Management API
"""
import os
import sys

import django

# Настройка Django окружения
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "freesport.settings")
django.setup()

import json

import requests

from apps.users.models import User

BASE_URL = "http://127.0.0.1:8001/api/v1"


def test_user_roles():
    """Тест получения ролей пользователей"""
    print("=== Тест получения ролей ===")
    response = requests.get(f"{BASE_URL}/users/roles/")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()


def test_user_registration():
    """Тест регистрации пользователя"""
    print("=== Тест регистрации пользователя ===")

    # Удаляем тестового пользователя если существует
    User.objects.filter(email="test@example.com").delete()

    data = {
        "email": "test@example.com",
        "password": "testpass123!",
        "password_confirm": "testpass123!",
        "first_name": "Test",
        "last_name": "User",
        "role": "retail",
    }

    response = requests.post(f"{BASE_URL}/auth/register/", json=data)
    print(f"Status: {response.status_code}")
    try:
        print(f"Response: {response.json()}")
    except:
        print(f"Response Text: {response.text}")
    print()
    return response.status_code == 201


def test_user_login():
    """Тест входа пользователя"""
    print("=== Тест входа пользователя ===")

    data = {"email": "test@example.com", "password": "testpass123!"}

    response = requests.post(f"{BASE_URL}/auth/login/", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

    if response.status_code == 200:
        return response.json().get("access")
    return None


def test_user_profile(access_token):
    """Тест получения профиля"""
    print("=== Тест получения профиля ===")

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/users/profile/", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()


if __name__ == "__main__":
    print("Запуск тестов User Management API\n")

    # Тест 1: Получение ролей
    test_user_roles()

    # Тест 2: Регистрация
    registration_success = test_user_registration()

    if registration_success:
        # Тест 3: Вход
        access_token = test_user_login()

        if access_token:
            # Тест 4: Профиль
            test_user_profile(access_token)
        else:
            print("❌ Не удалось получить access token")
    else:
        print("❌ Регистрация не удалась")

    print("Тесты завершены")
