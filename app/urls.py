from django.urls import path, include
from rest_framework import routers

from .views import ProjectGroupView, ProfileView, ProjectGroupLoadProjectsView, ProjectsView, RepositoryView, \
    GradeCategoryView, ProjectGroupGradingView, ProjectGradesView, RootAddUsers, MockAccounts, GradeUserView, \
    RepositoryUpdateView, ProjectGroupUpdateView, ProjectMilestonesView, ProjectMilestoneDataView, \
    ProjectMilestoneTimeSpentView, BulkGradeView, FeedbackView, GroupSummaryMilestoneDataView, \
    ProjectMilestoneConnectionsView, MilestoneSetGradeMilestoneView

router = routers.DefaultRouter()

urlpatterns = [
    path("groups/", ProjectGroupView.as_view(), name="groups"),
    path("groups/<int:id>/projects/", ProjectGroupLoadProjectsView.as_view(), name="load_projects"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("projects/<int:id>/", ProjectsView.as_view(), name="projects"),
    path("repositories/<int:id>/", RepositoryView.as_view(), name="repos"),
    path("grade_category/<int:id>/", GradeCategoryView.as_view(), name="grade_categories"),
    path("groups/<int:id>/grading/", ProjectGroupGradingView.as_view(), name="grading_system"),
    path("projects/<int:id>/grading/", ProjectGradesView.as_view(), name="project_grades"),
    path("groups/<int:id>/new_users/", RootAddUsers.as_view(), name="groups_add_users"),
    path("accounts/mock/", MockAccounts.as_view(), name="mock_accounts"),
    path("users/<int:user_id>/grade/<int:grade_id>/", GradeUserView.as_view(), name="grade_user"),
    path("repositories/<int:id>/update/", RepositoryUpdateView.as_view(), name="update_repository"),
    path("projects/<int:id>/update/", ProjectGroupUpdateView.as_view(), name="update_project_group"),
    path("projects/<int:id>/milestones/", ProjectMilestonesView.as_view(), name="project_milestones"),
    path("projects/<int:id>/milestone/<int:milestone_id>/", ProjectMilestoneDataView.as_view(), name="project_milestone_data"),
    path("projects/<int:id>/milestone/<int:milestone_id>/time_spent/", ProjectMilestoneTimeSpentView.as_view(), name="project_milestone_time_spent"),
    path("bulk_grade/", BulkGradeView.as_view(), name="bulk_grade"),
    path("feedback/", FeedbackView.as_view(), name="feedback"),
    path("groups/<int:id>/milestone/<int:milestone_id>/", GroupSummaryMilestoneDataView.as_view(), name="group_summary_project_milestone_data"),
    path("projects/<int:id>/milestone_connections/", ProjectMilestoneConnectionsView.as_view(), name="project_milestone_connections"),
    path("milestones/<int:id>/grade_milestone/", MilestoneSetGradeMilestoneView.as_view(), name="set_grade_milestone_for_milestone"),
    path('', include(router.urls)),
]
