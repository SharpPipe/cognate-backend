from rest_framework import serializers
from django.contrib.auth.models import User

from .models import ProjectGroup, Profile, Project, Repository, GradeCategory, GradeMilestone, UserGrade, UserProject, \
    Milestone, Process, Feedback, TimeSpent, Issue


class ProjectGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectGroup
        fields = ['id', 'children_type', 'name', 'description', 'group_id']

    def create(self, validated_data):
        return ProjectGroup.objects.create(**validated_data)


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'name']


class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = ['id', 'url', 'gitlab_id', 'name', 'project']


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['id', 'user_id', 'gitlab_token', 'actual_account']
        read_only_fields = ['user_id']


class RecursiveField(serializers.Serializer):
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data


class GradeMilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeMilestone
        fields = ['id', 'start', 'end', 'milestone_order_id']


class GradeCategorySerializer(serializers.ModelSerializer):
    children = RecursiveField(many=True, required=False)
    grademilestone = GradeMilestoneSerializer(required=False)

    class Meta:
        model = GradeCategory
        fields = ['id', 'name', 'total', 'grade_type', 'parent_category', 'description', 'children', 'grademilestone']


class AccountUsernameSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class UserProjectSerializer(serializers.ModelSerializer):
    account = AccountUsernameSerializer()

    class Meta:
        model = UserProject
        fields = ['id', 'account']


class UserGradeSerializer(serializers.ModelSerializer):
    user_project = UserProjectSerializer()

    class Meta:
        model = UserGrade
        fields = ['amount', 'user_project']
        # list_serializer_class = IsActiveListSerializer


class UserGradeListSerializer(serializers.ListSerializer):

    child = UserGradeSerializer()

    def to_representation(self, data):
        data = data.filter(user_project__in=self.child.context['user_projects'])
        return super(UserGradeListSerializer, self).to_representation(data)


class GradeCategorySerializerWithGrades(serializers.ModelSerializer):

    children = RecursiveField(many=True, required=False)
    grademilestone = GradeMilestoneSerializer(required=False)
    usergrade_set = UserGradeListSerializer()

    class Meta:
        model = GradeCategory
        fields = ['id', 'name', 'total', 'grade_type', 'parent_category', 'description', 'children', 'grademilestone', 'usergrade_set']


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


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = ['id', 'grade_milestone', 'repository', 'title', 'gitlab_id']


class ProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Process
        fields = ['id', 'hash', 'type', 'status', 'completion_percentage', 'data']


class FeedbackSerializer(serializers.ModelSerializer):
    commenter = AccountUsernameSerializer()

    class Meta:
        model = Feedback
        fields = ['text', 'time', 'commenter']


class LimitedIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Issue
        fields = ['title', 'gitlab_link']


class TimeSpentSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField(slug_field="username", read_only=True)
    issue = LimitedIssueSerializer()

    class Meta:
        model = TimeSpent
        fields = ['time', 'amount', 'user', 'issue']
