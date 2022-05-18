import decimal
import random

from .models import UserProject, AssessmentCategory, ProjectAssessment, UserAssessment, AutomateAssessment, TimeSpent, \
    Commit, Repository, AssessmentMilestone, Issue

from . import model_traversal


def add_assessments_to_category(assessment_category, project_group):
    for project in project_group.project_set.all():
        if assessment_category.project_assessment:
            add_project_assessment_recursive(project, assessment_category)
        else:
            for user_project in project.userproject_set.all():
                add_user_assessment_recursive(user_project, assessment_category)


def add_user_assessment_recursive(user_project, category):
    query = UserAssessment.objects.filter(user_project=user_project).filter(assessment_category=category)
    if query.count() == 0:
        UserAssessment.objects.create(amount=0, user_project=user_project, assessment_category=category)
    for child in category.children.all():
        if child.project_assessment:
            add_project_assessment_recursive(user_project.project, child)
        else:
            add_user_assessment_recursive(user_project, child)


def add_project_assessment_recursive(project, assessment_category):
    if ProjectAssessment.objects.filter(project=project).filter(assessment_category=assessment_category).count() == 0:
        ProjectAssessment.objects.create(amount=0, project=project, assessment_category=assessment_category)
    for child in assessment_category.children.all():
        add_project_assessment_recursive(project, child)


def add_user_assessment(user_project, project_group):
    root_category = project_group.assessment_calculation.assessment_category
    add_user_assessment_recursive(user_project, root_category)


def propagate_assessment_up(user, assessment_category):
    parent = assessment_category.parent_category
    if parent is None:
        return
    if parent.assessment_type not in "SMI":
        return

    if parent.project_assessment:
        if assessment_category.project_assessment:
            propagate_project_assessment_update_up(user, parent)
        else:
            # TODO: Maybe allow this some day
            pass
    else:
        if assessment_category.project_assessment:
            for dev in UserProject.objects.filter(project=user).filter(disabled=False).all():
                propagate_user_assessment_update_up(dev, user, parent)
        else:
            propagate_user_assessment_update_up(user, user.project, parent)


def propagate_user_assessment_update_up(user_project, project, parent):
    func = AssessmentCategory.ASSESSMENT_TYPE_FUNCS[parent.assessment_type]
    children = parent.children
    children_total_potential = func([c.total for c in children.all()])
    children_values = []
    for child in children.all():
        if child.project_assessment:
            children_values.append(
                pick_assessment(ProjectAssessment.objects.filter(project=project).filter(assessment_category=child)).amount)
        else:
            children_values.append(
                pick_assessment(UserAssessment.objects.filter(user_project=user_project).filter(assessment_category=child)).amount)
    children_total_value = func(children_values)

    amount = parent.total * children_total_value / children_total_potential
    assessment_query = UserAssessment.objects.filter(user_project=user_project).filter(assessment_category=parent)
    give_automated_assessment(amount, parent, user_project, assessment_query)
    if assessment_query.filter(assessment_type="M").count() > 0:
        return
    propagate_assessment_up(user_project, parent)


def propagate_project_assessment_update_up(project, parent):
    func = AssessmentCategory.ASSESSMENT_TYPE_FUNCS[parent.assessment_type]
    children = parent.children
    children_total_potential = func([c.total for c in children.all()])
    children_values = []
    for child in children.all():
        children_values.append(
            pick_assessment(ProjectAssessment.objects.filter(project=project).filter(assessment_category=child)).amount)
    children_total_value = func(children_values)

    amount = parent.total * children_total_value / children_total_potential
    assessment_query = ProjectAssessment.objects.filter(project=project).filter(assessment_category=parent)
    give_automated_project_assessment(amount, parent, project, assessment_query)
    if assessment_query.filter(assessment_type="M").count() > 0:
        return
    propagate_assessment_up(project, parent)


def pick_assessment(query):
    options = query.all()
    order = ["M", "A", "P"]
    for target_type in order:
        for option in options:
            if option.assessment_type == target_type:
                return option


def give_automated_project_assessment(amount, assessment_category, project, assessments_query):
    give_automated_assessment_general(amount, assessment_category, project, assessments_query, "project")


def give_automated_assessment(amount, assessment_category, user_project, assessments_query):
    give_automated_assessment_general(amount, assessment_category, user_project, assessments_query, "user")


def give_automated_assessment_general(amount, assessment_category, user, assessments_query, assessment_type):
    give_assessment(assessments_query, amount, assessment_type, "A", user, assessment_category)


def give_manual_assessment(query, amount, assessment_type, user, assessment_category):
    give_assessment(query, amount, assessment_type, "M", user, assessment_category)


def give_assessment(query, amount, grading_type, assessment_type, user, assessment_category):
    added_data = False
    for old_assessment in query.all():
        if old_assessment.assessment_type == "P":
            old_assessment.delete()
        elif old_assessment.assessment_type == assessment_type:
            old_assessment.amount = amount
            old_assessment.save()
            added_data = True
    if not added_data:
        if grading_type == "user":
            UserAssessment.objects.create(amount=amount, user_project=user, assessment_category=assessment_category, assessment_type=assessment_type)
        else:
            ProjectAssessment.objects.create(amount=amount, project=user, assessment_category=assessment_category, assessment_type=assessment_type)


def assessment_user(user_id, assessment_category, amount):
    user_project = UserProject.objects.filter(pk=user_id).first()
    search = UserAssessment.objects.filter(user_project=user_project).filter(assessment_category=assessment_category)
    give_manual_assessment(search, amount, "user", user_project, assessment_category)
    propagate_assessment_up(user_project, assessment_category)


def assessment_project(user_project_id, assessment_category, amount):
    project = UserProject.objects.filter(pk=user_project_id).first().project
    search = ProjectAssessment.objects.filter(project=project).filter(assessment_category=assessment_category)
    give_manual_assessment(search, amount, "project", project, assessment_category)
    propagate_assessment_up(project, assessment_category)


def assessment(target_id, assessment_id, amount):
    assessment_category = AssessmentCategory.objects.filter(pk=assessment_id).first()
    if assessment_category.project_assessment:
        assessment_project(target_id, assessment_category, amount)
    else:
        assessment_user(target_id, assessment_category, amount)


def get_child_assessments(child_user_assessments):
    child_assessments = []
    for child_user_assessment in child_user_assessments:
        q1 = child_user_assessment.filter(assessment_type="M")
        if q1.count() == 0:
            q2 = child_user_assessment.filter(assessment_type="A")
            if q2.count() == 0:
                child_assessments.append(0)
            else:
                child_assessments.append(q2.first().amount)
        else:
            child_assessments.append(q1.first().amount)
    return child_assessments


def recalculate_smi(assessment_category, children, child_user_assessments, user, query, assessment_give_function):
    func = AssessmentCategory.ASSESSMENT_TYPE_FUNCS[assessment_category.assessment_type]
    total_potential = func([child.total for child in children]) if len(children) > 0 else 0
    child_assessments = get_child_assessments(child_user_assessments)
    total_value = func(child_assessments) if len(child_assessments) > 0 else 0
    amount = assessment_category.total * total_value / total_potential if total_potential != 0 else 0
    assessment_give_function(amount, assessment_category, user, query)


def recalculate_project_assessment(assessment_category, project):
    children = assessment_category.children.all()
    for child in children:
        recalculate_project_assessment(child, project)

    if assessment_category.assessment_type in "SMI":
        child_user_assessments = [ProjectAssessment.objects.filter(assessment_category=child).filter(project=project) for child in children]
        user_assessment = ProjectAssessment.objects.filter(assessment_category=assessment_category).filter(project=project).filter(assessment_type="A")
        recalculate_smi(assessment_category, children, child_user_assessments, project, user_assessment, give_automated_project_assessment)
    elif assessment_category.assessment_type == "A":
        automation = AutomateAssessment.objects.filter(assessment_category=assessment_category)
        if automation.count() == 0:
            return
        automation = automation.first()
        user_assessment = ProjectAssessment.objects.filter(assessment_category=assessment_category).filter(project=project).filter(assessment_type="A")

        if automation.automation_type == "R":
            amount = random.random() * assessment_category.total  # TODO: Think about if assessment has already been rolled, should we roll it again
        elif automation.automation_type == "T":
            assessment_milestone = model_traversal.get_assessment_milestone_for_assessment_category(assessment_category)
            time_spent = get_time_spent_for_project_in_milestone(project, assessment_milestone)
            amount = decimal.Decimal(min(1, time_spent / automation.amount_needed)) * assessment_category.total
        elif automation.automation_type == "L":
            assessment_milestone = model_traversal.get_assessment_milestone_for_assessment_category(assessment_category)
            lines_added = get_lines_added_for_project_in_milestone(project, assessment_milestone)
            amount = decimal.Decimal(min(1, lines_added / automation.amount_needed)) * assessment_category.total
        give_automated_project_assessment(amount, assessment_category, project, user_assessment)


def recalculate_user_assessment(assessment_category, user_project):
    children = assessment_category.children.all()
    for child in children:
        if child.project_assessment:
            recalculate_project_assessment(child, user_project.project)
        else:
            recalculate_user_assessment(child, user_project)

    if assessment_category.assessment_type in "SMI":
        child_user_assessments = []
        for child in children:
            if child.project_assessment:
                child_user_assessments.append(ProjectAssessment.objects.filter(assessment_category=child).filter(project=user_project.project))
            else:
                child_user_assessments.append(UserAssessment.objects.filter(assessment_category=child).filter(user_project=user_project))

        user_assessment = UserAssessment.objects.filter(assessment_category=assessment_category).filter(user_project=user_project).filter(assessment_type="A")
        recalculate_smi(assessment_category, children, child_user_assessments, user_project, user_assessment, give_automated_assessment)
    elif assessment_category.assessment_type == "A":
        automation = AutomateAssessment.objects.filter(assessment_category=assessment_category)
        if automation.count() == 0:
            return
        automation = automation.first()
        user_assessment = UserAssessment.objects.filter(assessment_category=assessment_category).filter(user_project=user_project).filter(assessment_type="A")

        if automation.automation_type == "R":
            amount = random.random() * assessment_category.total  # TODO: Think about if assessment has already been rolled, should we roll it again
        elif automation.automation_type == "T":
            assessment_milestone = model_traversal.get_assessment_milestone_for_assessment_category(assessment_category)
            time_spent = get_time_spent_for_user_in_milestone(user_project, assessment_milestone)
            amount = decimal.Decimal(min(1, time_spent / automation.amount_needed)) * assessment_category.total
        elif automation.automation_type == "L":
            assessment_milestone = model_traversal.get_assessment_milestone_for_assessment_category(assessment_category)
            lines_added = get_lines_added_for_user_in_milestone(user_project, assessment_milestone)
            amount = decimal.Decimal(min(1, lines_added / automation.amount_needed)) * assessment_category.total
        give_automated_assessment(amount, assessment_category, user_project, user_assessment)


def recalculate_assessment_category(assessment_category):
    if assessment_category.project_assessment:
        for project in set([project_assessment.project for project_assessment in ProjectAssessment.objects.filter(assessment_category=assessment_category).all()]):
            recalculate_project_assessment(assessment_category, project)
    else:
        for user_project in set([user_assessment.user_project for user_assessment in UserAssessment.objects.filter(assessment_category=assessment_category).all()]):
            recalculate_user_assessment(assessment_category, user_project)


def get_time_spent_for_project_in_milestone(project, assessment_milestone):
    return sum([get_time_spent_for_user_in_milestone(user_project, assessment_milestone) for user_project in UserProject.objects.filter(project=project).filter(disabled=False).all()])


def get_issue_data_for_user_in_milestone(user_project, assessment_milestone):
    data = {}
    data["authored"] = Issue.objects\
        .filter(author=user_project.account)\
        .filter(milestone__assessment_milestone=assessment_milestone).count()
    data["closed"] = Issue.objects \
        .filter(closed_by=user_project.account) \
        .filter(milestone__assessment_milestone=assessment_milestone).count()
    data["participated"] = Issue.objects\
        .filter(timespent__user=user_project.account)\
        .filter(milestone__assessment_milestone=assessment_milestone).count()
    return data


def get_time_spent_for_user_in_milestone(user_project, assessment_milestone):
    times_spent = TimeSpent.objects.filter(user=user_project.account).filter(issue__milestone__assessment_milestone=assessment_milestone).all()
    return sum([time_spend.amount for time_spend in times_spent if assessment_milestone.start <= time_spend.time <= assessment_milestone.end]) / 60


def get_lines_added_for_project_in_milestone(project, assessment_milestone):
    return sum([get_lines_added_for_user_in_milestone(user_project, assessment_milestone) for user_project in UserProject.objects.filter(project=project).filter(disabled=False).all()])


def get_lines_added_for_user_in_milestone(user_project, assessment_milestone):
    project = user_project.project
    repos = Repository.objects.filter(project=project).all()
    commits = []
    for repo in repos:
        commits += [commit for commit in Commit.objects.filter(repository=repo).all() if assessment_milestone.start <= commit.time <= assessment_milestone.end]
    return sum([commit.lines_added for commit in commits])


def generate_assessment_category_copy(assessment_category, parent):
    new_category = AssessmentCategory.objects.create(
        name=assessment_category.name,
        total=assessment_category.total,
        assessment_type=assessment_category.assessment_type,
        description=assessment_category.description,
        project_assessment=assessment_category.project_assessment,
        parent_category=parent
    )
    if new_category.assessment_type == "A":
        old_automate_assessment = AutomateAssessment.objects.filter(assessment_category=assessment_category).first()
        AutomateAssessment.objects.create(
            automation_type=old_automate_assessment.automation_type,
            amount_needed=old_automate_assessment.amount_needed,
            assessment_category=new_category
        )
    gm_query = AssessmentMilestone.objects.filter(assessment_category=assessment_category)
    project_group = model_traversal.get_project_group_of_assessment_category_id(assessment_category.pk)
    if gm_query.count() > 0 :
        gm = gm_query.first()

        amount = model_traversal.get_amount_of_assessmentmilestone_by_projectgroup(project_group)
        AssessmentMilestone.objects.create(
            start=gm.start,
            end=gm.end,
            milestone_order_id=amount + 1,
            assessment_category=new_category
        )
    add_assessments_to_category(new_category, project_group)
    for child in assessment_category.children.all():
        generate_assessment_category_copy(child, new_category)


def assessment_category_has_milestone_parent(assessment_category):
    if AssessmentMilestone.objects.filter(assessment_category=assessment_category).count() > 0:
        return True
    if assessment_category.parent_category is None:
        return False
    return assessment_category_has_milestone_parent(assessment_category.parent_category)
