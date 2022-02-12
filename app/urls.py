from django.urls import path, include
from rest_framework import routers

from .views import ProjectGroupView, ProfileView, ProjectGroupLoadProjectsView, ProjectsView, RepositoryView, \
    GradeCategoryView, ProjectGroupGradingView, GradeComponentView, ProjectGradesView, RootAddUsers, MockAccounts

router = routers.DefaultRouter()

urlpatterns = [
    path("groups/", ProjectGroupView.as_view(), name="groups"),
    path("groups/<id>/projects/", ProjectGroupLoadProjectsView.as_view(), name="load_projects"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("projects/<id>/", ProjectsView.as_view(), name="projects"),
    path("repositories/<id>/", RepositoryView.as_view(), name="repos"),
    path("grade_category/<id>/", GradeCategoryView.as_view(), name="grade_categories"),
    path("grade_component/<id>/", GradeComponentView.as_view(), name="grade_components"),
    path("groups/<id>/grading/", ProjectGroupGradingView.as_view(), name="grading_system"),
    path("projects/<id>/grading/", ProjectGradesView.as_view(), name="project_grades"),
    path("groups/<id>/new_users/", RootAddUsers.as_view(), name="groups_add_users"),
    path("accounts/mock/", MockAccounts.as_view(), name="mock_accounts"),
    path('', include(router.urls)),
]
