from rest_framework import views
from rest_framework.mixins import (
    CreateModelMixin, ListModelMixin, RetrieveModelMixin, UpdateModelMixin
)
from django.http import JsonResponse

from django.contrib.auth.models import User
from .models import ProjectGroup, UserProjectGroup
from .serializers import ProjectGroupSerializer


class ProjectGroupViewSet(views.APIView):
    def get(self, request):
        queryset = ProjectGroup.objects.filter(user_project_groups__account=request.user)
        print([x for x in queryset])
        serializer = ProjectGroupSerializer(queryset, many=True)
        return JsonResponse(serializer.data, safe=False)
    # queryset = ProjectGroup.objects.all()
    # serializer_class = ProjectGroupSerializer
