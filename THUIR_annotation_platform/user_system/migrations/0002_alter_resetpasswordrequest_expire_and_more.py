# Generated by Django 4.2.20 on 2025-03-26 14:52

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user_system", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="resetpasswordrequest",
            name="expire",
            field=models.IntegerField(default=1743108763),
        ),
        migrations.AlterField(
            model_name="resetpasswordrequest",
            name="token",
            field=models.CharField(default="ad8a096bd04b", max_length=50),
        ),
    ]
