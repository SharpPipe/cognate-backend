from django.urls import path, include
from rest_framework import routers

from .views import ProjectGroupViewSet

router = routers.DefaultRouter()
router.register(r'groups', ProjectGroupViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
