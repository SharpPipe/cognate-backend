import datetime
import random

from django.contrib.auth.models import User
from django.db import models


def identifier_generator():
    return ''.join([random.choice("0123456789abcdef") for _ in range(32)])


class Profile(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    identifier = models.CharField(max_length=32, default=identifier_generator)
    gitlab_token = models.CharField(max_length=1000, null=True, blank=True)
    actual_account = models.BooleanField(default=True)
    gitlab_token_encrypted = models.BooleanField(default=False)
    gitlab_token_salt = models.CharField(max_length=1000, null=True, blank=True)
    store_passwords_in_local_storage = models.BooleanField(default=False)


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
    gitlab_token = models.CharField(max_length=1000, null=True, blank=True)

    def __str__(self):
        return f"({self.pk}) - {self.name}"


class ProjectGroupInvitation(models.Model):
    identifier = models.CharField(max_length=32)
    project_group = models.ForeignKey(ProjectGroup, on_delete=models.CASCADE, related_name="invitations")
    has_been_declined = models.BooleanField(default=False)


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
    last_issue_sync = models.DateTimeField(default=datetime.datetime.utcfromtimestamp(0))


class UserProject(models.Model):
    role_hierarchy = ["B", "V", "M", "E", "T", "A", "O"]  # Sorted from least to most

    class Roles(models.TextChoices):
        # We should define some hierarchy of these roles
        OWNER = ("O", "Owner")
        ADMIN = ("A", "Admin")
        TEACHER = ("T", "Teacher")
        MENTOR = ("E", "Mentor")
        MEMBER = ("M", "Member")
        VIEWER = ("V", "Viewer")
        BLANK = ("B", "Blank")

    rights = models.CharField(max_length=1, choices=Roles.choices, default=Roles.VIEWER)
    account = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    disabled = models.BooleanField(default=False)
    colour = models.CharField(max_length=8, null=True, blank=True)
    total_lines_added = models.IntegerField(default=0)
    total_lines_removed = models.IntegerField(default=0)

    def __str__(self):
        return self.account.username + " <-> " + self.project.name


class UserProjectGroup(models.Model):
    role_hierarchy = ["B", "V", "A", "O"]

    class Roles(models.TextChoices):
        OWNER = ("O", "Owner")
        ADMIN = ("A", "Admin")
        VIEWER = ("V", "Viewer")
        BLANK = ("B", "Blank")

    rights = models.CharField(max_length=1, choices=Roles.choices, default=Roles.VIEWER)
    account = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    project_group = models.ForeignKey(ProjectGroup, on_delete=models.CASCADE, related_name='user_project_groups')


class AssessmentCategory(models.Model):

    ASSESSMENT_TYPE_FUNCS = {
        "S": sum,
        "M": max,
        "I": min
    }

    class AssessmentType(models.TextChoices):
        CUSTOM = ("C", "Custom")
        SUM = ("S", "Sum")  # Assessment is sum of children, then scaled using total
        MAX = ("M", "Max")  # Assessment is max of children, then scaled using total
        MIN = ("I", "Min")  # Assessment is max of children, then scaled using total
        AUTOMATIC = ("A", "Automatic")  # Comes from script, also has an AutomateAssessment object tied to it

    name = models.CharField(max_length=200, null=True, blank=True)
    total = models.DecimalField(max_digits=100, decimal_places=5, default=1.0)
    assessment_type = models.CharField(max_length=1, choices=AssessmentType.choices, default=AssessmentType.CUSTOM)
    description = models.TextField(null=True, blank=True)
    project_assessment = models.BooleanField(default=False)
    parent_category = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    # This SET_NULL is a lifesaver, NEVER change


class AutomateAssessment(models.Model):
    class AutomationType(models.TextChoices):
        RANDOM = ("R", "Random")  # A random value between 0 and 1 is given
        TIME_SPENT = ("T", "Time spent")
        LINES_ADDED = ("L", "Lines added")  # Is actually the difference in lines, so added - removed
        UNIQUE_COMMIT_MESSAGES = ("CM", "Unique commit messages")
        WORD_COUNT_IN_COMMIT_MESSAGES = ("CW", "Average word count in commit messages")
        WORD_COUNT_IN_ISSUE_DESCRIPTIONS = ("IW", "Average word count in issue descriptions")
        ISSUE_AMOUNT = ("IA", "Issue amount")
        COMMIT_AMOUNT = ("CA", "Commit amount")

    automation_type = models.CharField(max_length=2, choices=AutomationType.choices, default=AutomationType.RANDOM)
    amount_needed = models.IntegerField()
    assessment_category = models.ForeignKey(AssessmentCategory, on_delete=models.CASCADE)


class AssessmentMilestone(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField()
    milestone_order_id = models.IntegerField()
    assessment_category = models.OneToOneField(AssessmentCategory, on_delete=models.CASCADE, null=True, blank=True, related_name="assessment_milestone")


class Milestone(models.Model):
    assessment_milestone = models.ForeignKey(AssessmentMilestone, on_delete=models.SET_NULL, null=True, blank=True)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="milestones", null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones", null=True, blank=True)
    title = models.TextField(null=True, blank=True)
    gitlab_id = models.IntegerField()
    gitlab_link = models.TextField(null=True, blank=True)


class Issue(models.Model):
    gitlab_id = models.IntegerField()
    title = models.TextField(null=True, blank=True)
    gitlab_iid = models.IntegerField()
    milestone = models.ForeignKey(Milestone, on_delete=models.SET_NULL, related_name="issues", null=True, blank=True)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="issues", null=True, blank=True)
    has_been_moved = models.BooleanField(default=False)
    gitlab_link = models.TextField(null=True, blank=True)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="issues_closed", null=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="issues_authored", null=True, blank=True)
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="issues_assigned", null=True, blank=True)
    description = models.TextField(null=True, blank=True)


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
    counted_in_user_project_total = models.BooleanField(default=False)


class AssessmentCalculation(models.Model):
    assessment_category = models.OneToOneField(AssessmentCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="assessment_calculation")
    project_group = models.OneToOneField(ProjectGroup, on_delete=models.CASCADE, related_name="assessment_calculation")


class AssessmentInstanceType(models.TextChoices):
    PLACEHOLDER = ("P", "Placeholder")  # Initial value
    AUTOMATIC = ("A", "Automatic")  # Generated by our enterprise level AI
    MANUAL = ("M", "Manual")  # Set by the inferior mentors


class UserAssessment(models.Model):
    assessment_instance_hierarchy = ["P", "A", "M"]

    assessment_type = models.CharField(max_length=1, choices=AssessmentInstanceType.choices, default=AssessmentInstanceType.PLACEHOLDER)
    amount = models.DecimalField(max_digits=100, decimal_places=5)
    user_project = models.ForeignKey(UserProject, on_delete=models.CASCADE, null=True, blank=True)
    assessment_category = models.ForeignKey(AssessmentCategory, on_delete=models.CASCADE)


class ProjectAssessment(models.Model):
    assessment_type = models.CharField(max_length=1, choices=AssessmentInstanceType.choices, default=AssessmentInstanceType.PLACEHOLDER)
    amount = models.DecimalField(max_digits=100, decimal_places=5)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    assessment_category = models.ForeignKey(AssessmentCategory, on_delete=models.CASCADE)


class Feedback(models.Model):
    class FeedbackType(models.TextChoices):
        APPLICATION = ("AP", "Application")              # Connections: None
        PROJECT = ("PA", "Project")                      # Connections: Project
        PROJECT_MILESTONE = ("PM", "Project milestone")  # Connections: Project, AssessmentMilestone
        USER = ("UA", "User")                            # Connections: UserProject
        USER_MILESTONE = ("UM", "User milestone")        # Connections: UserProject, AssessmentMilestone

    text = models.TextField(null=True, blank=True)
    type = models.CharField(max_length=2, choices=FeedbackType.choices)

    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name="feedback")
    user = models.ForeignKey(UserProject, on_delete=models.CASCADE, null=True, blank=True, related_name="feedback")
    assessment_milestone = models.ForeignKey(AssessmentMilestone, on_delete=models.CASCADE, null=True, blank=True, related_name="feedback")

    commenter = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    time = models.DateTimeField()


class Process(models.Model):
    class ProcessType(models.TextChoices):
        SYNC_GROUP = ("SG", "Sync group")
        SYNC_REPO = ("SR", "Sync repo")

    class ProcessStatus(models.TextChoices):
        ONGOING = ("O", "Ongoing")
        FINISHED = ("F", "Finished")

    hash = models.TextField()
    id_hash = models.TextField()
    type = models.CharField(max_length=2, choices=ProcessType.choices)
    status = models.CharField(max_length=1, choices=ProcessStatus.choices)
    completion_percentage = models.DecimalField(max_digits=6, decimal_places=3)
    data = models.JSONField(null=True, blank=True)
