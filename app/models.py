from django.db import models


class Committer(models.Model):
    uni_id = models.CharField(max_length=50)
    email = models.CharField(max_length=100)
    account = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)


class ProjectGroup(models.Model):
    class ChildrenType(models.TextChoices):
        GROUPS = ("G", "Groups")
        PROJECTS = ("P", "Projects")

    children_type = models.CharField(max_length=1, choices=ChildrenType.choices, default=ChildrenType.PROJECTS)
    name = models.CharField(max_length=50)
    description = models.TextField()
    parent_group = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)


class Project(models.Model):
    project_group = models.ForeignKey(ProjectGroup, on_delete=models.SET_NULL, null=True, blank=True)


class Repository(models.Model):
    url = models.CharField(max_length=100)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)


class UserProject(models.Model):
    class Rights(models.TextChoices):
        ADMIN = ("A", "Admin")
        OWNER = ("O", "Owner")
        VIEWER = ("V", "Viewer")

    rights = models.CharField(max_length=1, choices=Rights.choices, default=Rights.VIEWER)
    account = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)


class UserProjectGroup(models.Model):
    class Rights(models.TextChoices):
        ADMIN = ("A", "Admin")
        OWNER = ("O", "Owner")
        VIEWER = ("V", "Viewer")

    rights = models.CharField(max_length=1, choices=Rights.choices, default=Rights.VIEWER)
    account = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    project_group = models.ForeignKey(ProjectGroup, on_delete=models.CASCADE, related_name='user_project_groups')


class GradeCategory(models.Model):
    parent_category = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)


class GradeComponent(models.Model):
    total = models.IntegerField()
    # TODO: Add type enum?
    description = models.TextField()
    grade_category = models.ForeignKey(GradeCategory, on_delete=models.SET_NULL, null=True, blank=True)


class GradeMilestone(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField()
    grade_component = models.ForeignKey(GradeComponent, on_delete=models.CASCADE)


class Milestone(models.Model):
    grade_milestone = models.ForeignKey(GradeMilestone, on_delete=models.SET_NULL, null=True, blank=True)
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
    user = models.ForeignKey(Committer, on_delete=models.CASCADE)


class Commit(models.Model):
    hash = models.CharField(max_length=100)
    time = models.DateTimeField()
    message = models.TextField()
    lines_added = models.IntegerField()
    lines_removed = models.IntegerField()
    author = models.ForeignKey(Committer, on_delete=models.CASCADE)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)


class GradeCalculation(models.Model):
    grade_category = models.ForeignKey(GradeCategory, on_delete=models.SET_NULL, null=True, blank=True)
    project_group = models.ForeignKey(ProjectGroup, on_delete=models.CASCADE)


class UserGrade(models.Model):
    amount = models.IntegerField()
    account = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    grade_component = models.ForeignKey(GradeComponent, on_delete=models.CASCADE)



