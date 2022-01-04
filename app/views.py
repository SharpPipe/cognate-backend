from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import generics
from . models import GitlabGroup
from . serializers import GitlabGroupSerializer


class GitlabGroupsView(generics.RetrieveAPIView):
    queryset = GitlabGroup.objects.all()

    def get(self, request):
        queryset = self.get_queryset()
        serializer = GitlabGroupSerializer(queryset, many=True)
        return Response(serializer.data)
