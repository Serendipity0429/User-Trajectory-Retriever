# Generated by Django 4.2.20 on 2025-03-26 15:08

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user_system", "0004_alter_resetpasswordrequest_expire_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="resetpasswordrequest",
            name="expire",
            field=models.IntegerField(default=1743109693),
        ),
        migrations.AlterField(
            model_name="resetpasswordrequest",
            name="token",
            field=models.CharField(default="966a3d07dbee", max_length=50),
        ),
    ]
