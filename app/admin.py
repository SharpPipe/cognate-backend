from django.contrib import admin
from .models import *

admin.site.register(Profile)
admin.site.register(Committer)
admin.site.register(ProjectGroup)
admin.site.register(Project)
admin.site.register(Repository)
admin.site.register(UserProject)
admin.site.register(UserProjectGroup)
admin.site.register(GradeCategory)
admin.site.register(GradeMilestone)
admin.site.register(Milestone)
admin.site.register(Issue)
admin.site.register(TimeSpent)
admin.site.register(Commit)
admin.site.register(GradeCalculation)
admin.site.register(UserGrade)
admin.site.register(AutomateGrade)
