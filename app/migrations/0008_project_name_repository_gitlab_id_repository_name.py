# Generated by Django 4.0 on 2022-02-04 13:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0007_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='repository',
            name='gitlab_id',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='repository',
            name='name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]