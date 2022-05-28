from django.urls import path
from rest_framework import routers

from .views import ProjectGroupView, ProfileView, ProjectGroupLoadProjectsView, ProjectsView, RepositoryView, \
    AssessmentCategoryView, ProjectGroupAssessmentView, ProjectAssessmentsView, AssessUserView, RepositoryUpdateView, \
    ProjectGroupUpdateView, ProjectMilestoneDataView, ProjectMilestoneTimeSpentView, BulkAssessView, FeedbackView, \
    GroupSummaryMilestoneDataView, ProjectMilestoneConnectionsView, MilestoneSetAssessmentMilestoneView, TestLoginView, \
    ProcessInfoView, AssessmentCategoryRecalculateView, ParametricTimeSpentView, ChangeDevColourView, \
    ProjectRepoConnectionView, RepoSetProjectView, AddNewProject, AddNewRepo, AssessmentCategoryCopyView, \
    ManageGroupInvitationsView, ProfileInvitationView, AcceptGroupInvitationView, ProjectGroupUsersView, \
    ProjectUsersView

router = routers.DefaultRouter()

urlpatterns = [
    path("groups/<int:id>/", ProjectsView.as_view(), name="projects"),
    path("groups/<int:id>/users/", ProjectGroupUsersView.as_view(), name="project_group_users"),
    path("groups/<int:id>/project/", AddNewProject.as_view(), name="add_new_project"),
    path("groups/<int:id>/project_repo_connections/", ProjectRepoConnectionView.as_view(), name="project_repo_connections"),
    path("groups/<int:id>/assessment/", ProjectGroupAssessmentView.as_view(), name="assessment_system"),
    path("groups/<int:id>/milestone/<int:milestone_id>/", GroupSummaryMilestoneDataView.as_view(), name="group_summary_project_milestone_data"),
    path("groups/<int:id>/invitations/", ManageGroupInvitationsView.as_view(), name="invite_user_to_project_group"),
    path("groups/<int:id>/accept_invitation/", AcceptGroupInvitationView.as_view(), name="accept_group_invitation"),

    path("assessment_category/<int:id>/", AssessmentCategoryView.as_view(), name="assessment_categories"),
    path("assessment_category/<int:id>/copy/", AssessmentCategoryCopyView.as_view(), name="copy_assessment_category"),
    path("assessment_category/<int:id>/recalculate/", AssessmentCategoryRecalculateView.as_view(), name="recalculate_assessment_category"),

    path("groups/<int:id>/projects/", ProjectGroupLoadProjectsView.as_view(), name="load_projects"),
    path("groups/<int:id>/update/", ProjectGroupUpdateView.as_view(), name="update_project_group"),

    path("projects/<int:id>/", RepositoryView.as_view(), name="repos"),
    path("projects/<int:id>/milestone/<int:milestone_id>/", ProjectMilestoneDataView.as_view(), name="project_milestone_data"),
    path("projects/<int:id>/milestone/<int:milestone_id>/time_spent/", ProjectMilestoneTimeSpentView.as_view(), name="project_milestone_time_spent"),
    path("projects/<int:id>/time_spent/", ParametricTimeSpentView.as_view(), name="parametric_time_spent"),

    path("projects/<int:id>/change_dev_colour/", ChangeDevColourView.as_view(), name="change_dev_colour"),
    path("projects/<int:id>/users/", ProjectUsersView.as_view(), name="project_users"),
    path("projects/<int:id>/repo/", AddNewRepo.as_view(), name="add_new_repo"),
    path("repos/<int:id>/project/", RepoSetProjectView.as_view(), name="set_project_for_repo"),
    path("projects/<int:id>/milestone_connections/", ProjectMilestoneConnectionsView.as_view(), name="project_milestone_connections"),
    path("milestones/<int:id>/assessment_milestone/", MilestoneSetAssessmentMilestoneView.as_view(), name="set_assessment_milestone_for_milestone"),
    path("repositories/<int:id>/update/", RepositoryUpdateView.as_view(), name="update_repository"),

    path("projects/<int:id>/assessments/", ProjectAssessmentsView.as_view(), name="project_assessments"),
    path("users/<int:user_id>/assess/<int:assessment_id>/", AssessUserView.as_view(), name="assess_user"),
    path("bulk_assess/", BulkAssessView.as_view(), name="bulk_assess"),

    path("groups/", ProjectGroupView.as_view(), name="groups"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("invitations/", ProfileInvitationView.as_view(), name="invitations"),

    path("process/<int:id>/<str:hash>/", ProcessInfoView.as_view(), name="get_process_info"),
    path("feedback/", FeedbackView.as_view(), name="feedback"),
    path("", TestLoginView.as_view(), name="test_login"),
]
