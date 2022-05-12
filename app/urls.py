from django.urls import path
from rest_framework import routers

from .views import ProjectGroupView, ProfileView, ProjectGroupLoadProjectsView, ProjectsView, RepositoryView, \
    GradeCategoryView, ProjectGroupGradingView, ProjectGradesView, GradeUserView, RepositoryUpdateView, \
    ProjectGroupUpdateView, ProjectMilestoneDataView, ProjectMilestoneTimeSpentView, BulkGradeView, FeedbackView, \
    GroupSummaryMilestoneDataView, ProjectMilestoneConnectionsView, MilestoneSetGradeMilestoneView, TestLoginView, \
    ProcessInfoView, ProjectAddUserView, GradeCategoryRecalculateView, ParametricTimeSpentView, ChangeDevColourView, \
    ProjectRepoConnectionView, RepoSetProjectView, AddNewProject, AddNewRepo, GradeCategoryCopyView

router = routers.DefaultRouter()

urlpatterns = [
    path("groups/<int:id>/", ProjectsView.as_view(), name="projects"),
    path("groups/<int:id>/project/", AddNewProject.as_view(), name="add_new_project"),
    path("groups/<int:id>/project_repo_connections/", ProjectRepoConnectionView.as_view(), name="project_repo_connections"),
    path("groups/<int:id>/grading/", ProjectGroupGradingView.as_view(), name="grading_system"),
    path("groups/<int:id>/milestone/<int:milestone_id>/", GroupSummaryMilestoneDataView.as_view(), name="group_summary_project_milestone_data"),

    path("grade_category/<int:id>/", GradeCategoryView.as_view(), name="grade_categories"),
    path("grade_category/<int:id>/copy/", GradeCategoryCopyView.as_view(), name="copy_grade_category"),
    path("grade_category/<int:id>/recalculate/", GradeCategoryRecalculateView.as_view(), name="recalculate_grade_category"),

    path("groups/<int:id>/projects/", ProjectGroupLoadProjectsView.as_view(), name="load_projects"),
    path("projects/<int:id>/update/", ProjectGroupUpdateView.as_view(), name="update_project_group"),

    path("projects/<int:id>/", RepositoryView.as_view(), name="repos"),
    path("projects/<int:id>/milestone/<int:milestone_id>/", ProjectMilestoneDataView.as_view(), name="project_milestone_data"),
    path("projects/<int:id>/milestone/<int:milestone_id>/time_spent/", ProjectMilestoneTimeSpentView.as_view(), name="project_milestone_time_spent"),
    path("projects/<int:id>/time_spent/", ParametricTimeSpentView.as_view(), name="parametric_time_spent"),

    path("projects/<int:id>/change_dev_colour/", ChangeDevColourView.as_view(), name="change_dev_colour"),
    path("projects/<int:id>/add_user/", ProjectAddUserView.as_view(), name="add_user_to_project"),
    path("projects/<int:id>/repo/", AddNewRepo.as_view(), name="add_new_repo"),
    path("repos/<int:id>/project/", RepoSetProjectView.as_view(), name="set_project_for_repo"),
    path("projects/<int:id>/milestone_connections/", ProjectMilestoneConnectionsView.as_view(), name="project_milestone_connections"),
    path("milestones/<int:id>/grade_milestone/", MilestoneSetGradeMilestoneView.as_view(), name="set_grade_milestone_for_milestone"),
    path("repositories/<int:id>/update/", RepositoryUpdateView.as_view(), name="update_repository"),

    path("projects/<int:id>/grading/", ProjectGradesView.as_view(), name="project_grades"),
    path("users/<int:user_id>/grade/<int:grade_id>/", GradeUserView.as_view(), name="grade_user"),
    path("bulk_grade/", BulkGradeView.as_view(), name="bulk_grade"),

    path("groups/", ProjectGroupView.as_view(), name="groups"),
    path("profile/", ProfileView.as_view(), name="profile"),

    path("process/<int:id>/<str:hash>/", ProcessInfoView.as_view(), name="get_process_info"),
    path("feedback/", FeedbackView.as_view(), name="feedback"),
    path("", TestLoginView.as_view(), name="test_login"),
]
