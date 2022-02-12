from django.urls import path, include
from rest_framework import routers

from .views import ProjectGroupView, ProfileView, ProjectGroupLoadProjectsView, ProjectsView, RepositoryView, GradeCategoryView

router = routers.DefaultRouter()

urlpatterns = [
    path("groups/", ProjectGroupView.as_view(), name="groups"),
    path("groups/<id>/projects/", ProjectGroupLoadProjectsView.as_view(), name="load_projects"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("projects/<id>/", ProjectsView.as_view(), name="projects"),
    path("repositories/<id>/", RepositoryView.as_view(), name="repos"),
    path("grade_category/<id>/", GradeCategoryView.as_view(), name="grade_categories"),
    path('', include(router.urls)),
]
