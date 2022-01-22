from django.urls import path, include
from rest_framework import routers

from .views import ProjectGroupViewSet

router = routers.DefaultRouter()
# router.register(r'groups', ProjectGroupViewSet, basename="groups")

urlpatterns = [
    path("groups/", ProjectGroupViewSet.as_view(), name="groups"),
    path('', include(router.urls)),
]
