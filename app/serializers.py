from rest_framework import serializers

from .models import ProjectGroup


class ProjectGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectGroup
        fields = ['id', 'children_type', 'name', 'description', 'group_id']

    def create(self, validated_data):
        print("CREATING")
        return ProjectGroup.objects.create(**validated_data)


