# Generated by Django 4.2.20 on 2025-03-27 14:24

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user_system", "0002_alter_resetpasswordrequest_expire_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="resetpasswordrequest",
            name="expire",
            field=models.IntegerField(default=1743193446),
        ),
        migrations.AlterField(
            model_name="resetpasswordrequest",
            name="token",
            field=models.CharField(default="b5be3c34dfd1", max_length=50),
        ),
    ]
