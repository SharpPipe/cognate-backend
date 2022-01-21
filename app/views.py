from rest_framework import viewsets

from .models import ProjectGroup
from .serializers import ProjectGroupSerializer


class ProjectGroupViewSet(viewsets.ModelViewSet):
    queryset = ProjectGroup.objects.all()
    serializer_class = ProjectGroupSerializer
