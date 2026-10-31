# Generated manually for cart constraints

from django.db import migrations
from django.db.models import CheckConstraint, Q


class Migration(migrations.Migration):
    dependencies = [
        ("cart", "0001_initial"),
    ]

    operations = [
        # Check constraints для корзины
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=CheckConstraint(
                condition=Q(quantity__gte=1), name="cart_items_quantity_positive"
            ),
        ),
        # Бизнес-правило: у корзины должен быть либо пользователь, либо session_key
        migrations.AddConstraint(
            model_name="cart",
            constraint=CheckConstraint(
                condition=Q(user__isnull=False) | Q(session_key__isnull=False),
                name="carts_user_or_session_required",
            ),
        ),
    ]
