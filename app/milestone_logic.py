
from .models import Project, UserProject, GradeCategory, UserGrade, ProjectGrade, Feedback

from .serializers import FeedbackSerializer

from . import model_traversal
from . import grading_tree


def get_milestone_data_for_project(request, id, milestone_id):
    project = Project.objects.filter(pk=id).first()
    milestone = model_traversal.get_grademilestone_by_projectgroup_and_milestone_order_number(project.project_group, milestone_id)
    if milestone is None:
        return {"status": 418, "error": f"Milestone {milestone_id} not found for project {id}."}

    promised_json = []

    user_projects = UserProject.objects.filter(project=project).filter(disabled=False).all()
    for user_project in user_projects:
        user_list = []
        total_time = grading_tree.get_time_spent_for_user_in_milestone(user_project, milestone)
        promised_json.append({
            "username": user_project.account.username,
            "colour": user_project.colour,
            "id": user_project.pk,
            "spent_time": total_time,
            "data": user_list
        })
        for grade_category in GradeCategory.objects.filter(parent_category=milestone.grade_category).filter(project_grade=False).all():
            category_data = {}
            user_list.append(category_data)

            category_data["name"] = grade_category.name
            category_data["total"] = grade_category.total
            category_data["automatic_points"] = None
            category_data["given_points"] = None
            category_data["description"] = grade_category.description
            category_data["id"] = grade_category.pk

            grading_tree.recalculate_user_grade(grade_category, user_project)
            user_grades = UserGrade.objects.filter(grade_category=grade_category).filter(user_project=user_project)

            for user_grade in user_grades.all():
                if user_grade.grade_type == "A":
                    category_data["automatic_points"] = user_grade.amount
                elif user_grade.grade_type == "M":
                    category_data["given_points"] = user_grade.amount

    project_grades = []
    for grade_category in GradeCategory.objects.filter(parent_category=milestone.grade_category).filter(project_grade=True).all():
        category_data = {}
        project_grades.append(category_data)
        category_data["name"] = grade_category.name
        category_data["total"] = grade_category.total
        category_data["automatic_points"] = None
        category_data["given_points"] = None
        category_data["description"] = grade_category.description
        category_data["id"] = grade_category.pk

        grading_tree.recalculate_project_grade(grade_category, project)
        grades = ProjectGrade.objects.filter(grade_category=grade_category).filter(project=project)
        for grade in grades.all():
            if grade.grade_type == "A":
                category_data["automatic_points"] = grade.amount
            elif grade.grade_type == "M":
                category_data["given_points"] = grade.amount
    return {"status": 200, "project_name": project.name, "users_data": promised_json, "project_data": project_grades}


def get_grademilestone_data_for_project(project, grade_milestones, detailed=False):
    milestones = []
    for grade_milestone in grade_milestones:
        this_milestone = {}
        milestones.append(this_milestone)
        this_milestone["milestone_id"] = grade_milestone.milestone_order_id
        milestone_category = grade_milestone.grade_category
        milestone_users = []
        this_milestone["user_points"] = milestone_users
        graded = False
        for dev in project.userproject_set.filter(disabled=False).all():
            user_grade = UserGrade.objects.filter(grade_category=milestone_category).filter(user_project=dev).first()
            # TODO: think of a better way to determine this
            if user_grade.amount > 0:
                graded = True
            dev_data = {
                "name": dev.account.username,
                "colour": dev.colour,
                "points": user_grade.amount,
                "time_spent": grading_tree.get_time_spent_for_user_in_milestone(dev, grade_milestone)
            }
            if detailed:
                grades = {}
                for sub_grade in UserGrade.objects.filter(grade_category__parent_category=milestone_category).filter(user_project=dev).filter(grade_type="M").all():
                    grades[sub_grade.grade_category.name] = sub_grade.amount
                dev_data["grades"] = grades
            milestone_users.append(dev_data)
        milestone_links = []
        for milestone in grade_milestone.milestone_set.filter(repository__project=project).all():
            milestone_links.append(milestone.gitlab_link)
        this_milestone["gitlab_links"] = milestone_links
        feedback = Feedback.objects.filter(type="PM").filter(project=project).filter(
            grade_milestone=grade_milestone).all()
        this_milestone["milestone_feedback"] = FeedbackSerializer(feedback, many=True).data

        if detailed:
            this_milestone["graded"] = graded
            this_milestone["start_time"] = grade_milestone.start
            this_milestone["end_time"] = grade_milestone.end

    milestones.sort(key=lambda x: x["milestone_id"])
    return milestones
