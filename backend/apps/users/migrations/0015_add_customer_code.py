from django.core.validators import RegexValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0014_make_company_fields_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="customer_code",
            field=models.CharField(
                blank=True,
                max_length=5,
                null=True,
                unique=True,
                validators=[
                    RegexValidator(regex="^\\d{5}$", message="Код клиента должен содержать ровно 5 цифр")
                ],
                verbose_name="Код клиента",
            ),
        ),
    ]
