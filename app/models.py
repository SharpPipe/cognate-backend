from django.db import models


class Profile(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    gitlab_token = models.CharField(max_length=1000, null=True, blank=True)


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
    group_id = models.IntegerField(null=True, blank=True)
    parent_group = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)


class Project(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    project_group = models.ForeignKey(ProjectGroup, on_delete=models.SET_NULL, null=True, blank=True)


class Repository(models.Model):
    url = models.CharField(max_length=100)
    gitlab_id = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
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
    name = models.CharField(max_length=200, null=True, blank=True)
    parent_category = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)


class GradeComponent(models.Model):
    class GradeType(models.TextChoices):
        CUSTOM = ("C", "Custom")

    total = models.IntegerField()
    grade_type = models.CharField(max_length=1, choices=GradeType.choices, default=GradeType.CUSTOM)
    description = models.TextField()
    grade_category = models.ForeignKey(GradeCategory, on_delete=models.SET_NULL, null=True, blank=True)


class GradeMilestone(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField()
    grade_category = models.OneToOneField(GradeCategory, on_delete=models.CASCADE, null=True, blank=True)


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
    grade_category = models.OneToOneField(GradeCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="grade_calculation")
    project_group = models.OneToOneField(ProjectGroup, on_delete=models.CASCADE, related_name="grade_calculation")


class UserGrade(models.Model):
    amount = models.IntegerField()
    account = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    grade_component = models.ForeignKey(GradeComponent, on_delete=models.CASCADE)



