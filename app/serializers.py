from rest_framework import serializers

from django.contrib.auth.models import User
from .models import ProjectGroup


class ProjectGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectGroup
        fields = ['children_type', 'name', 'description']
