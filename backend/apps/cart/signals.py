"""
Сигналы для корзины покупок
"""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Cart, CartItem


@receiver(pre_save, sender=CartItem)
def update_reserved_quantity_on_save(sender, instance, **kwargs):
    """
    Обновляет зарезервированное количество варианта товара до сохранения CartItem.
    """
    if instance.pk:  # Если это обновление существующего объекта
        try:
            old_instance = CartItem.objects.get(pk=instance.pk)
            quantity_diff = instance.quantity - old_instance.quantity
        except CartItem.DoesNotExist:
            quantity_diff = instance.quantity
    else:  # Если это создание нового объекта
        quantity_diff = instance.quantity

    variant = instance.variant
    variant.reserved_quantity += quantity_diff
    variant.save(update_fields=["reserved_quantity"])


@receiver(post_delete, sender=CartItem)
def update_reserved_quantity_on_delete(sender, instance, **kwargs):
    """
    Уменьшает зарезервированное количество варианта товара после удаления CartItem.
    """
    variant = instance.variant
    variant.reserved_quantity -= instance.quantity
    # Убедимся, что резерв не станет отрицательным
    if variant.reserved_quantity < 0:
        variant.reserved_quantity = 0
    variant.save(update_fields=["reserved_quantity"])


User = get_user_model()


@receiver(post_save, sender=User)
def merge_guest_cart_on_login(sender, instance, created, **kwargs):
    """
    Перенос гостевой корзины при авторизации пользователя
    """
    if not created:  # Срабатывает только при обновлении, не при создании
        return

    # Ищем гостевую корзину в текущей сессии
    request = getattr(instance, "_request", None)
    if not request or not hasattr(request, "session"):
        return

    session_key = request.session.session_key
    if not session_key:
        return

    try:
        guest_cart = Cart.objects.get(session_key=session_key, user__isnull=True)

        # Получаем или создаем корзину пользователя
        user_cart, created = Cart.objects.get_or_create(user=instance)

        if guest_cart.items.exists():
            # Переносим товары из гостевой корзины
            for guest_item in guest_cart.items.all():
                try:
                    # Проверяем, есть ли уже такой вариант в корзине пользователя
                    user_item = CartItem.objects.get(cart=user_cart, variant=guest_item.variant)
                    # Если есть, увеличиваем количество
                    user_item.quantity += guest_item.quantity
                    user_item.save()
                except CartItem.DoesNotExist:
                    # Если нет, создаем новый элемент с price_snapshot
                    CartItem.objects.create(
                        cart=user_cart,
                        variant=guest_item.variant,
                        quantity=guest_item.quantity,
                        price_snapshot=guest_item.price_snapshot,
                    )

            # Удаляем гостевую корзину
            guest_cart.delete()

    except Cart.DoesNotExist:
        # Гостевой корзины нет, ничего не делаем
        pass
