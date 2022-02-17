from django.urls import path, include
from rest_framework import routers

from .views import ProjectGroupView, ProfileView, ProjectGroupLoadProjectsView, ProjectsView, RepositoryView, \
    GradeCategoryView, ProjectGroupGradingView, ProjectGradesView, RootAddUsers, MockAccounts, GradeUserView, \
    RepositoryUpdateView, ProjectGroupUpdateView, ProjectMilestonesView, ProjectMilestoneDataView, \
    ProjectMilestoneTimeSpentView, BulkGradeView, FeedbackView

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
    path("projects/<id>/update/", ProjectGroupUpdateView.as_view(), name="update_project_group"),
    path("projects/<id>/milestones/", ProjectMilestonesView.as_view(), name="project_milestones"),
    path("projects/<id>/milestone/<milestone_id>", ProjectMilestoneDataView.as_view(), name="project_milestone_data"),
    path("projects/<id>/milestone/<milestone_id>/time_spent", ProjectMilestoneTimeSpentView.as_view(), name="project_milestone_time_spent"),
    path("bulk_grade/", BulkGradeView.as_view(), name="bulk_grade"),
    path("feedback/", FeedbackView.as_view(), name="feedback"),
    path('', include(router.urls)),
]
