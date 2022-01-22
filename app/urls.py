from django.urls import path, include
from rest_framework import routers

from .views import ProjectGroupView, ProfileView

router = routers.DefaultRouter()

urlpatterns = [
    path("groups/", ProjectGroupView.as_view(), name="groups"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path('', include(router.urls)),
]
