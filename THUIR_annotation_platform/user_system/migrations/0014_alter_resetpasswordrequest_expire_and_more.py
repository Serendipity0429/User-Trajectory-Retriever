# Generated by Django 4.2.20 on 2025-03-11 08:13

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user_system", "0013_alter_resetpasswordrequest_expire_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="resetpasswordrequest",
            name="expire",
            field=models.IntegerField(default=1741788812),
        ),
        migrations.AlterField(
            model_name="resetpasswordrequest",
            name="token",
            field=models.CharField(default="56ba48303e61", max_length=50),
        ),
    ]
