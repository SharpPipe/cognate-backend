import string

import requests
import random

from rest_framework import views
from django.http import JsonResponse
from django.contrib.auth.models import User

from .models import ProjectGroup, UserProjectGroup, Profile, Project, Repository, GradeCategory, GradeCalculation, \
    GradeMilestone, UserProject
from .serializers import ProjectGroupSerializer, ProfileSerializer, ProjectSerializer, RepositorySerializer, \
    GradeCategorySerializer, GradeComponentSerializer, RegisterSerializer, UserSerializer


class ProjectGroupView(views.APIView):
    def get(self, request):
        queryset = ProjectGroup.objects.filter(user_project_groups__account=request.user)
        serializer = ProjectGroupSerializer(queryset, many=True)
        return JsonResponse(serializer.data, safe=False)

    def post(self, request):
        serializer = ProjectGroupSerializer(data=request.data)
        if serializer.is_valid():
            project_group = serializer.save()
            UserProjectGroup.objects.create(rights="O", account=request.user, project_group=project_group)
            grade_category = GradeCategory.objects.create(name="root")
            grade_calculation = GradeCalculation.objects.create(grade_category=grade_category, project_group=project_group)
        return JsonResponse({})


class ProjectGroupLoadProjectsView(views.APIView):
    def get(self, request, id):
        # x8xkGpUazyPda_ecaGtG
        print(f"Getting projects for project group {id}")
        group = ProjectGroup.objects.filter(pk=id).first()
        print(f"Project group is {group} with gitlab group id {group.group_id}")
        profile = Profile.objects.filter(user=request.user).first()
        print(f"User's provided auth token is {profile.gitlab_token}")

        base_url = "https://gitlab.cs.ttu.ee"
        api_part = "/api/v4"
        endpoint_part = f"/groups/{group.group_id}/projects"
        token_part = f"?private_token={profile.gitlab_token}"

        answer = requests.get(base_url + api_part + endpoint_part + token_part)
        print(f"Got response")

        json = answer.json()
        if not isinstance(json, list):
            error = f"Something went wrong, expected 'json' variable to be a list, but was {type(json)} instead.\n"
            error += f"'json' value: {json}"
            print(error)
            return JsonResponse({"error": error})
        data = []
        print(json)
        for project in json:
            data.append({
                "name": project["name"],
                "id": project["id"],
                "url": project["web_url"]
            })
            project_object = Project.objects.create(name=project["name_with_namespace"], project_group=group)
            Repository.objects.create(url=project["web_url"], gitlab_id=project["id"], name=project["name"], project=project_object)

        return JsonResponse({"data": data})


class ProjectsView(views.APIView):
    def get(self, request, id):
        group = ProjectGroup.objects.filter(pk=id).first()
        projects = Project.objects.filter(project_group=group)
        serializer = ProjectSerializer(projects, many=True)
        return JsonResponse(serializer.data, safe=False)


class RepositoryView(views.APIView):
    def get(self, request, id):
        project = Project.objects.filter(pk=id).first()
        repos = Repository.objects.filter(project=project)
        serializer = RepositorySerializer(repos, many=True)
        return JsonResponse(serializer.data, safe=False)


class ProfileView(views.APIView):
    def put(self, request):
        profile = Profile.objects.filter(user=request.user).first()
        profile.gitlab_token = request.data["gitlab_token"]
        profile.save()
        return JsonResponse({})


class GradeCategoryView(views.APIView):
    def post(self, request, id):
        serializer = GradeCategorySerializer(data=request.data)
        parent = GradeCategory.objects.filter(pk=id).first()

        # Validate that user has correct access rights
        root = parent
        while root.parent_category is not None:
            root = root.parent_category
        project_group = root.grade_calculation.project_group
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project_group)
        allowed_rights = ["A", "O"]
        has_rights = user_project_groups.count() > 0 and user_project_groups.first().rights in allowed_rights

        if has_rights and serializer.is_valid():
            grade_category = serializer.save()
            grade_category.parent_category = parent
            grade_category.save()
            if "start" in request.data.keys() and "end" in request.data.keys():
                grade_milestone = GradeMilestone.objects.create(start=request.data["start"], end=request.data["end"], grade_category=grade_category)
            return JsonResponse(GradeCategorySerializer(grade_category).data)
        return JsonResponse({4: 18})


class GradeComponentView(views.APIView):
    def post(self, request, id):
        serializer = GradeComponentSerializer(data=request.data)
        parent = GradeCategory.objects.filter(pk=id).first()

        # Validate that user has correct access rights
        root = parent
        while root.parent_category is not None:
            root = root.parent_category
        project_group = root.grade_calculation.project_group
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project_group)
        allowed_rights = ["A", "O"]
        has_rights = user_project_groups.count() > 0 and user_project_groups.first().rights in allowed_rights

        if has_rights and serializer.is_valid():
            grade_component = serializer.save()
            grade_component.grade_category = parent
            grade_component.save()
            return JsonResponse(GradeComponentSerializer(grade_component).data)
        return JsonResponse({4: 20})


class ProjectGroupGradingView(views.APIView):
    def get(self, request, id):
        project_group = ProjectGroup.objects.filter(pk=id).first()
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project_group)
        if user_project_groups.count() == 0:
            return JsonResponse({4: 18})
        root_category = project_group.grade_calculation.grade_category
        print(root_category)
        return JsonResponse(GradeCategorySerializer(root_category).data)


class ProjectGradesView(views.APIView):
    def get(self, request, id):
        project = Project.objects.filter(pk=id).first()
        user_projects = UserProject.objects.filter(account=request.user).filter(project=project)
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project.project_group)
        if user_project_groups.count() == 0:
            # TODO: If user_projects has users, then the request came from student, he should see his own grades.
            return JsonResponse({4: 18})
        members = project.userproject_set
        project_group_admins = project.project_group.user_project_groups
        print(members)
        print(project_group_admins.count())
        print(project.project_group)
        return JsonResponse({6: 9})


class RootAddUsers(views.APIView):
    def post(self, request, id):
        if not request.user.is_superuser:
            return JsonResponse({4: 18})

        users = request.data["data"]
        user_objects = []
        for user in users:
            email = user + "@ttu.ee"
            sub_data = {}
            sub_data["username"] = user
            sub_data["email"] = email
            sub_data["password"] = "".join([random.choice(string.ascii_lowercase) for _ in range(20)])
            sub_data["password_confirm"] = sub_data["password"]
            if "." in user:
                sub_data["first_name"] = user.split(".")[0]
                sub_data["last_name"] = ".".join(user.split(".")[1:])
            else:
                sub_data["first_name"] = user[:len(user) // 2]
                sub_data["last_name"] = user[len(user) // 2:]
            serializer = RegisterSerializer(data=sub_data)
            serializer.is_valid()
            user_object = serializer.save()
            Profile.objects.create(user=user_object, actual_account=False)
            user_objects.append(user_object)

        project_group = ProjectGroup.objects.filter(pk=id).first()
        projects = Project.objects.filter(project_group=project_group)
        for project in projects:
            users_found = []
            for repo in project.repository_set.all():
                repo_data = RepositorySerializer(repo).data

                base_url = "https://gitlab.cs.ttu.ee"
                api_part = "/api/v4"
                endpoint_part = f"/projects/{repo_data['gitlab_id']}/members/all"
                token_part = f"?private_token={request.user.profile.gitlab_token}"

                answer = requests.get(base_url + api_part + endpoint_part + token_part)
                answer_json = answer.json()

                for member in answer_json:
                    for user in user_objects:
                        if user.username in users_found:
                            continue
                        if member["username"] == user.username:
                            UserProject.objects.create(rights="M", account=user, project=project)
                            users_found.append(user.username)
                            print(f"{member['username']} found in project {project.name}")
        return JsonResponse({200: "OK"})


class MockAccounts(views.APIView):
    def get(self, request):
        accounts = User.objects.filter(profile__actual_account=False)
        return JsonResponse([x.id for x in accounts], safe=False)
