
from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    gitlab_token = models.CharField(max_length=1000, null=True, blank=True)
    actual_account = models.BooleanField(default=True)


class Committer(models.Model):
    name = models.CharField(max_length=250)
    email = models.CharField(max_length=250)
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

    def __str__(self):
        return self.name


class Project(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    project_group = models.ForeignKey(ProjectGroup, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name


class Repository(models.Model):
    url = models.CharField(max_length=100)
    gitlab_id = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)


class UserProject(models.Model):
    rights_hierarchy = ["V", "M", "E", "T", "A", "O"]  # Sorted from least to most

    class Rights(models.TextChoices):
        # We should define some hierarchy of these roles
        OWNER = ("O", "Owner")
        ADMIN = ("A", "Admin")
        TEACHER = ("T", "Teacher")
        MENTOR = ("E", "Mentor")
        MEMBER = ("M", "Member")
        VIEWER = ("V", "Viewer")

    rights = models.CharField(max_length=1, choices=Rights.choices, default=Rights.VIEWER)
    account = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    disabled = models.BooleanField(default=False)
    colour = models.CharField(max_length=6, null=True, blank=True)

    def __str__(self):
        return self.account.username + " <-> " + self.project.name


class UserProjectGroup(models.Model):
    class Rights(models.TextChoices):
        OWNER = ("O", "Owner")
        ADMIN = ("A", "Admin")
        VIEWER = ("V", "Viewer")

    rights = models.CharField(max_length=1, choices=Rights.choices, default=Rights.VIEWER)
    account = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    project_group = models.ForeignKey(ProjectGroup, on_delete=models.CASCADE, related_name='user_project_groups')


class GradeCategory(models.Model):
    class GradeType(models.TextChoices):
        CUSTOM = ("C", "Custom")
        SUM = ("S", "Sum")  # Grade is sum of children, then scaled using total
        MAX = ("M", "Max")  # Grade is max of children, then scaled using total
        MIN = ("I", "Min")  # Grade is max of children, then scaled using total
        AUTOMATIC = ("A", "Automatic")  # Comes from script, also has an AutomateGrade object tied to it

    name = models.CharField(max_length=200, null=True, blank=True)
    total = models.DecimalField(max_digits=100, decimal_places=5, default=1.0)
    grade_type = models.CharField(max_length=1, choices=GradeType.choices, default=GradeType.CUSTOM)
    description = models.TextField(null=True, blank=True)
    parent_category = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    # This SET_NULL is a lifesaver, NEVER change


class AutomateGrade(models.Model):
    class AutomationType(models.TextChoices):
        RANDOM = ("R", "Random")  # A random value between 0 and 1 is given
        TIME_SPENT = ("T", "Time spent")
        LINES_ADDED = ("L", "Lines added")  # Is actually the difference in lines, so added - removed

    automation_type = models.CharField(max_length=1, choices=AutomationType.choices, default=AutomationType.RANDOM)
    amount_needed = models.IntegerField()
    grade_category = models.ForeignKey(GradeCategory, on_delete=models.CASCADE)


class GradeMilestone(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField()
    milestone_order_id = models.IntegerField()
    grade_category = models.OneToOneField(GradeCategory, on_delete=models.CASCADE, null=True, blank=True)


class Milestone(models.Model):
    grade_milestone = models.ForeignKey(GradeMilestone, on_delete=models.SET_NULL, null=True, blank=True)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="milestones")
    title = models.TextField(null=True, blank=True)
    gitlab_id = models.IntegerField()
    gitlab_link = models.TextField(null=True, blank=True)


class Issue(models.Model):
    gitlab_id = models.IntegerField()
    title = models.TextField(null=True, blank=True)
    gitlab_iid = models.IntegerField()
    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE, related_name="issues", null=True, blank=True)
    has_been_moved = models.BooleanField(default=False)
    gitlab_link = models.TextField(null=True, blank=True)


class TimeSpent(models.Model):
    gitlab_id = models.IntegerField()
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
    author = models.ForeignKey(Committer, on_delete=models.CASCADE)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)


class GradeCalculation(models.Model):
    grade_category = models.OneToOneField(GradeCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="grade_calculation")
    project_group = models.OneToOneField(ProjectGroup, on_delete=models.CASCADE, related_name="grade_calculation")


class UserGrade(models.Model):
    class UserGradeType(models.TextChoices):
        PLACEHOLDER = ("P", "Placeholder")  # Initial value
        AUTOMATIC = ("A", "Automatic")  # Generated by our enterprise level AI
        MANUAL = ("M", "Manual")  # Set by the inferior mentors
    grade_type = models.CharField(max_length=1, choices=UserGradeType.choices, default=UserGradeType.PLACEHOLDER)
    amount = models.DecimalField(max_digits=100, decimal_places=5)
    user_project = models.ForeignKey(UserProject, on_delete=models.CASCADE, null=True, blank=True)
    grade_category = models.ForeignKey(GradeCategory, on_delete=models.CASCADE)


class Feedback(models.Model):
    class FeedbackType(models.TextChoices):
        APPLICATION = ("AP", "Application")              # Connections: None
        PROJECT = ("PA", "Project")                      # Connections: Project
        PROJECT_MILESTONE = ("PM", "Project milestone")  # Connections: Project, GradeMilestone
        USER = ("UA", "User")                            # Connections: UserProject
        USER_MILESTONE = ("UM", "User milestone")        # Connections: UserProject, GradeMilestone

    text = models.TextField(null=True, blank=True)
    type = models.CharField(max_length=2, choices=FeedbackType.choices)

    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name="feedback")
    user = models.ForeignKey(UserProject, on_delete=models.CASCADE, null=True, blank=True, related_name="feedback")
    grade_milestone = models.ForeignKey(GradeMilestone, on_delete=models.CASCADE, null=True, blank=True, related_name="feedback")

    commenter = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    time = models.DateTimeField()


class Process(models.Model):
    class ProcessType(models.TextChoices):
        SYNC_GROUP = ("SG", "Sync group")

    class ProcessStatus(models.TextChoices):
        ONGOING = ("O", "Ongoing")
        FINISHED = ("F", "Finished")

    hash = models.TextField()
    id_hash = models.TextField()
    type = models.CharField(max_length=2, choices=ProcessType.choices)
    status = models.CharField(max_length=1, choices=ProcessStatus.choices)
    completion_percentage = models.DecimalField(max_digits=6, decimal_places=3)
    data = models.JSONField(null=True, blank=True)
