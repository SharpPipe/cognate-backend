from django.db import models


class User(models.Model):
    uni_id = models.CharField(max_length=50)
    password_hash = models.CharField(max_length=100)


class ProjectGroup(models.Model):
    project_group = models.ForeignKey('self', on_delete=models.SET_NULL)


class Project(models.Model):
    project_group = models.ForeignKey(ProjectGroup, on_delete=models.SET_NULL)


class Repository(models.Model):
    url = models.CharField(max_length=100)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)


class UserProject(models.Model):
    class Rights(models.TextChoices):
        ADMIN = "A", _("Admin")
        OWNER = "O", _("Owner")
        VIEWER = "V", _("Viewer")

    rights = models.CharField(max_length=1, choices=Rights.choices, default=Rights.VIEWER)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)


class GradeCategory(models.Model):
    parent_category = models.ForeignKey('self', on_delete=models.SET_NULL)


class GradeComponent(models.Model):
    total = models.IntegerField()
    # TODO: Add type enum?
    description = models.TextField()
    grade_category = models.ForeignKey(GradeCategory, on_delete=models.SET_NULL)


class GradeMilestone(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField()
    grade_component = models.ForeignKey(GradeComponent, on_delete=models.CASCADE)


class Milestone(models.Model):
    grade_milestone = models.ForeignKey(GradeMilestone, on_delete=models.SET_NULL)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)


class Issue(models.Model):
    pass


class IssueMilestone(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField()
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE)
    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE)


class TimeSpent(models.Model):
    amount = models.IntegerField()
    time = models.DateTimeField()
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class Commit(models.Model):
    hash = models.CharField(max_length=100)
    time = models.DateTimeField()
    message = models.TextField()
    lines_added = models.IntegerField()
    lines_removed = models.IntegerField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)


class GradeCalculation(models.Model):
    grade_category = models.ForeignKey(ProjectGroup, on_delete=models.SET_NULL)
    project_group = models.ForeignKey(ProjectGroup, on_delete=models.CASCADE)


class UserGrade(models.Model):
    amount = models.IntegerField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    grade_component = models.ForeignKey(GradeComponent, on_delete=models.CASCADE)



