from rest_framework import serializers
from django.contrib.auth.models import User

from .models import ProjectGroup, Profile, Project, Repository, AssessmentCategory, AssessmentMilestone, \
    UserAssessment, UserProject, Milestone, Process, Feedback, TimeSpent, Issue


class ProjectGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectGroup
        fields = ['id', 'children_type', 'name', 'description', 'group_id']
        optional_fields = ['group_id']

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


class AssessmentMilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentMilestone
        fields = ['id', 'start', 'end', 'milestone_order_id']


class AssessmentCategorySerializer(serializers.ModelSerializer):
    children = RecursiveField(many=True, required=False)
    assessmentmilestone = AssessmentMilestoneSerializer(required=False)

    class Meta:
        model = AssessmentCategory
        fields = ['id', 'name', 'total', 'assessment_type', 'project_assessment', 'parent_category', 'description', 'children', 'assessmentmilestone']


class AccountUsernameSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class UserProjectSerializer(serializers.ModelSerializer):
    account = AccountUsernameSerializer()

    class Meta:
        model = UserProject
        fields = ['id', 'account', 'colour']


class UserAssessmentSerializer(serializers.ModelSerializer):
    user_project = UserProjectSerializer()

    class Meta:
        model = UserAssessment
        fields = ['amount', 'user_project']
        # list_serializer_class = IsActiveListSerializer


class UserAssessmentListSerializer(serializers.ListSerializer):

    child = UserAssessmentSerializer()

    def to_representation(self, data):
        data = data.filter(user_project__in=self.child.context['user_projects'])
        return super(UserAssessmentListSerializer, self).to_representation(data)


class AssessmentCategorySerializerWithAssessments(serializers.ModelSerializer):

    children = RecursiveField(many=True, required=False)
    assessmentmilestone = AssessmentMilestoneSerializer(required=False)
    userassessment_set = UserAssessmentListSerializer()

    class Meta:
        model = AssessmentCategory
        fields = ['id', 'name', 'total', 'assessment_type', 'project_assessment', 'parent_category', 'description', 'children', 'assessmentmilestone', 'userassessment_set']


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
        fields = ['id', 'assessment_milestone', 'repository', 'title', 'gitlab_id', 'gitlab_link']


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
