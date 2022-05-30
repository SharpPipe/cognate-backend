
from .models import Project, UserProject, AssessmentCategory, UserAssessment, ProjectAssessment, Feedback

from .serializers import FeedbackSerializer

from . import model_traversal
from . import assessment_tree


def get_milestone_data_for_project(request, id, milestone_id):
    project = Project.objects.filter(pk=id).first()
    milestone = model_traversal.get_assessmentmilestone_by_projectgroup_and_milestone_order_number(project.project_group, milestone_id)
    if milestone is None:
        return {"status": 418, "error": f"Milestone {milestone_id} not found for project {id}."}

    promised_json = []

    user_projects = UserProject.objects.filter(project=project).filter(disabled=False).all()
    for user_project in user_projects:
        user_list = []
        total_time = assessment_tree.get_time_spent_for_user_in_milestone(user_project, milestone)
        promised_json.append({
            "username": user_project.account.username,
            "colour": user_project.colour,
            "id": user_project.pk,
            "spent_time": total_time,
            "data": user_list
        })
        for assessment_category in AssessmentCategory.objects.filter(parent_category=milestone.assessment_category).filter(project_assessment=False).all():
            category_data = {}
            user_list.append(category_data)

            category_data["name"] = assessment_category.name
            category_data["total"] = assessment_category.total
            category_data["automatic_points"] = None
            category_data["given_points"] = None
            category_data["description"] = assessment_category.description
            category_data["id"] = assessment_category.pk

            assessment_tree.recalculate_user_assessment(assessment_category, user_project)
            user_assessments = UserAssessment.objects.filter(assessment_category=assessment_category).filter(user_project=user_project)

            for user_assessment in user_assessments.all():
                if user_assessment.assessment_type == "A":
                    category_data["automatic_points"] = user_assessment.amount
                elif user_assessment.assessment_type == "M":
                    category_data["given_points"] = user_assessment.amount

    project_assessments = []
    for assessment_category in AssessmentCategory.objects.filter(parent_category=milestone.assessment_category).filter(project_assessment=True).all():
        category_data = {}
        project_assessments.append(category_data)
        category_data["name"] = assessment_category.name
        category_data["total"] = assessment_category.total
        category_data["automatic_points"] = None
        category_data["given_points"] = None
        category_data["description"] = assessment_category.description
        category_data["id"] = assessment_category.pk

        assessment_tree.recalculate_project_assessment(assessment_category, project)
        assessments = ProjectAssessment.objects.filter(assessment_category=assessment_category).filter(project=project)
        for assessment in assessments.all():
            if assessment.assessment_type == "A":
                category_data["automatic_points"] = assessment.amount
            elif assessment.assessment_type == "M":
                category_data["given_points"] = assessment.amount
    return {"status": 200, "project_name": project.name, "users_data": promised_json, "project_data": project_assessments}


def get_assessmentmilestone_data_for_project(project, assessment_milestones, detailed=False):
    milestones = []
    for assessment_milestone in assessment_milestones:
        this_milestone = {}
        milestones.append(this_milestone)
        this_milestone["milestone_id"] = assessment_milestone.milestone_order_id
        milestone_category = assessment_milestone.assessment_category
        milestone_users = []
        this_milestone["user_points"] = milestone_users
        assessed = False
        for dev in project.userproject_set.filter(disabled=False).all():
            user_assessment = UserAssessment.objects.filter(assessment_category=milestone_category).filter(user_project=dev).first()
            amount = user_assessment.amount if user_assessment is not None else 0
            # TODO: think of a better way to determine this
            if amount > 0:
                assessed = True
            dev_data = {
                "name": dev.account.username,
                "colour": dev.colour,
                "points": amount
            }
            dev_data["time_spent"] = assessment_tree.get_time_spent_for_user_in_milestone(dev, assessment_milestone)
            dev_data["issues"] = assessment_tree.get_issue_data_for_user_in_milestone(dev, assessment_milestone)
            if detailed:
                assessments = {}
                for sub_assessment in UserAssessment.objects.filter(assessment_category__parent_category=milestone_category).filter(user_project=dev).filter(assessment_type="M").all():
                    assessments[sub_assessment.assessment_category.name] = sub_assessment.amount
                dev_data["assessments"] = assessments
            milestone_users.append(dev_data)
        milestone_links = []
        for milestone in assessment_milestone.milestone_set.filter(repository__project=project).all():
            milestone_links.append(milestone.gitlab_link)
        this_milestone["gitlab_links"] = milestone_links
        feedback = Feedback.objects.filter(type="PM").filter(project=project).filter(
            assessment_milestone=assessment_milestone).all()
        this_milestone["milestone_feedback"] = FeedbackSerializer(feedback, many=True).data
        if detailed:
            this_milestone["assessed"] = assessed
            this_milestone["start_time"] = assessment_milestone.start
            this_milestone["end_time"] = assessment_milestone.end

    milestones.sort(key=lambda x: x["milestone_id"])
    return milestones
