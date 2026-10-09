import secrets

import apps.common.models
from django.db import migrations, models


def populate_unsubscribe_tokens(apps, schema_editor):
    newsletter = apps.get_model("common", "Newsletter")
    for subscription in newsletter.objects.filter(unsubscribe_token__isnull=True).iterator():
        subscription.unsubscribe_token = secrets.token_urlsafe(32)
        subscription.save(update_fields=["unsubscribe_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0020_userconsent_source_valid"),
    ]

    operations = [
        migrations.AddField(
            model_name="newsletter",
            name="unsubscribe_token",
            field=models.CharField(
                editable=False,
                max_length=43,
                null=True,
                unique=True,
                verbose_name="Токен отписки",
            ),
        ),
        migrations.RunPython(populate_unsubscribe_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="newsletter",
            name="unsubscribe_token",
            field=models.CharField(
                default=apps.common.models.generate_unsubscribe_token,
                editable=False,
                max_length=43,
                unique=True,
                verbose_name="Токен отписки",
            ),
        ),
    ]
