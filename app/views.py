import requests

from rest_framework import views
from django.http import JsonResponse

from .models import ProjectGroup, UserProjectGroup, Profile, Project, Repository
from .serializers import ProjectGroupSerializer, ProfileSerializer, ProjectSerializer, RepositorySerializer


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
        return JsonResponse({})


class ProjectGroupLoadProjectsView(views.APIView):
    def get(self, request, id):
        # x8xkGpUazyPda_ecaGtG
        print(f"Getting projects for project group {id}")
        group = ProjectGroup.objects.filter(pk=id).first()
        print(f"Project group is {group} with gitlab group id {group.group_id}")
        profile = Profile.objects.filter(user=request.user).first()
        print(f"User's provided auth token is {profile.gitlab_token}")

        # gl = gitlab.Gitlab('https://gitlab.cs.ttu.ee', private_token=profile.gitlab_token, api_version='4')
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
        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
        return JsonResponse({})
