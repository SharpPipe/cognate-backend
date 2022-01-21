from rest_framework import viewsets

from django.contrib.auth.models import User
from .models import ProjectGroup
from .serializers import ProjectGroupSerializer


class ProjectGroupViewSet(viewsets.ModelViewSet):
    queryset = ProjectGroup.objects.all()
    serializer_class = ProjectGroupSerializer
