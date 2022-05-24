# Generated by Kristjan Kõiv on 2022-05-14 14:58

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0058_repository_last_issue_sync'),
    ]

    operations = [
        migrations.RenameModel('GradeCategory', 'AssessmentCategory'),
        migrations.RenameModel('AutomateGrade', 'AutomateAssessment'),
        migrations.RenameModel('GradeMilestone', 'AssessmentMilestone'),
        migrations.RenameModel('GradeCalculation', 'AssessmentCalculation'),
        migrations.RenameModel('UserGrade', 'UserAssessment'),
        migrations.RenameModel('ProjectGrade', 'ProjectAssessment'),
    ]