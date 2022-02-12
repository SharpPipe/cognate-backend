from rest_framework import serializers
from django.contrib.auth.models import User

from .models import ProjectGroup, Profile, Project, Repository, GradeCategory, GradeComponent


class ProjectGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectGroup
        fields = ['id', 'children_type', 'name', 'description', 'group_id']

    def create(self, validated_data):
        return ProjectGroup.objects.create(**validated_data)


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'name', 'project_group']


class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = ['id', 'url', 'gitlab_id', 'name', 'project']


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['id', 'user_id', 'gitlab_token']
        read_only_fields = ['user_id']


class RecursiveField(serializers.Serializer):
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data


class GradeComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeComponent
        fields = ['id', 'total', 'grade_type', 'description', 'grade_category']


class GradeCategorySerializer(serializers.ModelSerializer):
    gradecategory_set = RecursiveField(many=True)
    gradecomponent_set = GradeComponentSerializer(many=True)

    class Meta:
        model = GradeCategory
        fields = ['id', 'name', 'parent_category', 'gradecategory_set', 'gradecomponent_set']


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField()
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    password = serializers.CharField()
    password_confirm = serializers.CharField()

    def create(self, validated_data):
        user = User.objects.create_user(validated_data['username'], password=validated_data['password'], first_name=validated_data['first_name'], last_name=validated_data['last_name'], email=validated_data['email'])
        return user

    def validate(self, data):
        if not data.get('password') or not data.get('password_confirm'):
            raise serializers.ValidationError("Please enter a password and confirm it.")
        if data.get('password') != data.get('password_confirm'):
            raise serializers.ValidationError("Those passwords don't match.")
        return data


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'
