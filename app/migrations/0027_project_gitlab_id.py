# Generated by Django 4.0 on 2022-02-16 19:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0026_timespent_gitlab_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='gitlab_id',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
    ]
