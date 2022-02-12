from django.urls import path, include
from rest_framework import routers

from .views import ProjectGroupView, ProfileView, ProjectGroupLoadProjectsView, ProjectsView, RepositoryView, \
    GradeCategoryView, ProjectGroupGradingView, ProjectGradesView, RootAddUsers, MockAccounts, GradeUserView, \
    RepositoryUpdateView

router = routers.DefaultRouter()

urlpatterns = [
    path("groups/", ProjectGroupView.as_view(), name="groups"),
    path("groups/<id>/projects/", ProjectGroupLoadProjectsView.as_view(), name="load_projects"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("projects/<id>/", ProjectsView.as_view(), name="projects"),
    path("repositories/<id>/", RepositoryView.as_view(), name="repos"),
    path("grade_category/<id>/", GradeCategoryView.as_view(), name="grade_categories"),
    path("groups/<id>/grading/", ProjectGroupGradingView.as_view(), name="grading_system"),
    path("projects/<id>/grading/", ProjectGradesView.as_view(), name="project_grades"),
    path("groups/<id>/new_users/", RootAddUsers.as_view(), name="groups_add_users"),
    path("accounts/mock/", MockAccounts.as_view(), name="mock_accounts"),
    path("users/<user_id>/grade/<grade_id>/", GradeUserView.as_view(), name="grade_user"),
    path("repositories/<id>/update/", RepositoryUpdateView.as_view(), name="update_repository"),
    path('', include(router.urls)),
]
