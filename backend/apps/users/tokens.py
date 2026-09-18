"""
Token generator для password reset
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator

# Используем встроенный Django PasswordResetTokenGenerator напрямую
# Нет необходимости в кастомном классе для стандартного функционала
password_reset_token = PasswordResetTokenGenerator()
