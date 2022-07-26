# Generated by Django 4.0 on 2022-01-21 18:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_commit_gradecalculation_gradecategory_gradecomponent_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='projectgroup',
            old_name='project_group',
            new_name='parent_group',
        ),
        migrations.AddField(
            model_name='projectgroup',
            name='children_type',
            field=models.CharField(choices=[('G', 'Groups'), ('P', 'Projects')], default='P', max_length=1),
        ),
        migrations.AddField(
            model_name='projectgroup',
            name='description',
            field=models.TextField(default='Sample description'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='projectgroup',
            name='name',
            field=models.CharField(default='Sample name', max_length=50),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name='UserProjectGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rights', models.CharField(choices=[('A', 'Admin'), ('O', 'Owner'), ('V', 'Viewer')], default='V', max_length=1)),
                ('project_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.projectgroup')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.user')),
            ],
        ),
    ]
