# Generated by Django 4.0 on 2022-05-29 12:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0067_profile_gitlab_token_encrypted'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='gitlab_token_salt',
            field=models.CharField(blank=True, max_length=16, null=True),
        ),
    ]