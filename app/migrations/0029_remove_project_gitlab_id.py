# Generated by Django 4.0 on 2022-02-16 22:22

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0028_usergrade_grade_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='project',
            name='gitlab_id',
        ),
    ]