from django.urls import path
from . views import GitlabGroupsView

urlpatterns = [
    path('groups/', GitlabGroupsView.as_view(), name='gitlab-groups-view')
]
