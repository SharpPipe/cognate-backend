from rest_framework import views
from django.http import JsonResponse

from .models import ProjectGroup, UserProjectGroup, Profile
from .serializers import ProjectGroupSerializer, ProfileSerializer


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


class ProfileView(views.APIView):
    def put(self, request):
        profile = Profile.objects.filter(user=request.user).first()
        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
        return JsonResponse({})
