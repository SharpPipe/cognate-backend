from rest_framework import serializers
from . models import GitlabGroup


class GitlabGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = GitlabGroup
        fields = '__all__'
