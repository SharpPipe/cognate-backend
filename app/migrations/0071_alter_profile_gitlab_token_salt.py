# Generated by Django 4.0 on 2022-05-29 12:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0070_alter_profile_gitlab_token_salt'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='gitlab_token_salt',
            field=models.BinaryField(blank=True, editable=True, null=True),
        ),
    ]