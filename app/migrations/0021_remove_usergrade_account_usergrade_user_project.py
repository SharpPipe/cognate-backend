# Generated by Django 4.0 on 2022-02-12 19:10

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0020_alter_gradecategory_grade_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='usergrade',
            name='account',
        ),
        migrations.AddField(
            model_name='usergrade',
            name='user_project',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='app.userproject'),
        ),
    ]
