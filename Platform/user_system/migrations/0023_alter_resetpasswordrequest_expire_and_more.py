# Generated by Django 5.2.2 on 2025-06-20 00:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0022_alter_resetpasswordrequest_expire_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resetpasswordrequest',
            name='expire',
            field=models.IntegerField(default=1750488985),
        ),
        migrations.AlterField(
            model_name='resetpasswordrequest',
            name='token',
            field=models.CharField(default='4e2cb02c3a7f', max_length=50),
        ),
    ]
