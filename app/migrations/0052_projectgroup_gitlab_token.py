# Generated by Django 4.0 on 2022-04-16 07:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0051_alter_userproject_colour'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectgroup',
            name='gitlab_token',
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
    ]