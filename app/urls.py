from django.urls import path, include
from rest_framework import routers

from .views import ProjectGroupView

router = routers.DefaultRouter()

urlpatterns = [
    path("groups/", ProjectGroupView.as_view(), name="groups"),
    path('', include(router.urls)),
]
