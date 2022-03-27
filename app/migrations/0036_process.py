# Generated by Django 4.0 on 2022-03-27 14:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0035_issue_has_been_moved'),
    ]

    operations = [
        migrations.CreateModel(
            name='Process',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hash', models.TextField()),
                ('type', models.CharField(choices=[('SG', 'Sync group')], max_length=2)),
                ('status', models.CharField(choices=[('O', 'Ongoing'), ('F', 'Finished')], max_length=1)),
                ('completion_percentage', models.DecimalField(decimal_places=3, max_digits=6)),
            ],
        ),
    ]
