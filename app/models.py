from django.db import models


class GitlabGroup(models.Model):
    group_name = models.CharField(max_length=50)
    description = models.TextField()
    gitlab_id = models.IntegerField()
    hidden = models.BooleanField(default=False)

    def __str__(self):
        return self.group_name
