# Generated by Django 4.0 on 2022-02-12 18:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0018_alter_gradecategory_parent_category'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gradecategory',
            name='total',
            field=models.DecimalField(decimal_places=5, default=1.0, max_digits=100),
        ),
        migrations.AlterField(
            model_name='usergrade',
            name='amount',
            field=models.DecimalField(decimal_places=5, max_digits=100),
        ),
    ]