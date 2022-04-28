import decimal
import random

from .models import UserProject, GradeCategory, ProjectGrade, UserGrade, Project, AutomateGrade, TimeSpent, Commit, \
    Repository, GradeMilestone, Issue

from . import model_traversal


def add_grades_to_category(grade_category, project_group):
    for project in project_group.project_set.all():
        if grade_category.project_grade:
            add_project_grade_recursive(project, grade_category)
        else:
            for user_project in project.userproject_set.all():
                add_user_grade_recursive(user_project, grade_category)


def add_user_grade_recursive(user_project, category):
    query = UserGrade.objects.filter(user_project=user_project).filter(grade_category=category)
    if query.count() == 0:
        UserGrade.objects.create(amount=0, user_project=user_project, grade_category=category)
    for child in category.children.all():
        if child.project_grade:
            add_project_grade_recursive(user_project.project, child)
        else:
            add_user_grade_recursive(user_project, child)


def add_project_grade_recursive(project, grade_category):
    if ProjectGrade.objects.filter(project=project).filter(grade_category=grade_category).count() == 0:
        ProjectGrade.objects.create(amount=0, project=project, grade_category=grade_category)
    for child in grade_category.children.all():
        add_project_grade_recursive(project, child)


def add_user_grade(user_project, project_group):
    root_category = project_group.grade_calculation.grade_category
    add_user_grade_recursive(user_project, root_category)


def propagate_grade_up(user, grade_category):
    parent = grade_category.parent_category
    if parent is None:
        return
    if parent.grade_type not in "SMI":
        return

    if parent.project_grade:
        if grade_category.project_grade:
            propagate_project_grade_update_up(user, parent)
        else:
            # TODO: Maybe allow this some day
            pass
    else:
        if grade_category.project_grade:
            for dev in UserProject.objects.filter(project=user).filter(disabled=False).all():
                propagate_user_grade_update_up(dev, user, parent)
        else:
            propagate_user_grade_update_up(user, user.project, parent)


def propagate_user_grade_update_up(user_project, project, parent):
    func = GradeCategory.GRADE_TYPE_FUNCS[parent.grade_type]
    children = parent.children
    children_total_potential = func([c.total for c in children.all()])
    children_values = []
    for child in children.all():
        if child.project_grade:
            children_values.append(
                pick_grade(ProjectGrade.objects.filter(project=project).filter(grade_category=child)).amount)
        else:
            children_values.append(
                pick_grade(UserGrade.objects.filter(user_project=user_project).filter(grade_category=child)).amount)
    children_total_value = func(children_values)

    amount = parent.total * children_total_value / children_total_potential
    grade_query = UserGrade.objects.filter(user_project=user_project).filter(grade_category=parent)
    give_automated_grade(amount, parent, user_project, grade_query)
    if grade_query.filter(grade_type="M").count() > 0:
        return
    propagate_grade_up(user_project, parent)


def propagate_project_grade_update_up(project, parent):
    func = GradeCategory.GRADE_TYPE_FUNCS[parent.grade_type]
    children = parent.children
    children_total_potential = func([c.total for c in children.all()])
    children_values = []
    for child in children.all():
        children_values.append(
            pick_grade(ProjectGrade.objects.filter(project=project).filter(grade_category=child)).amount)
    children_total_value = func(children_values)

    amount = parent.total * children_total_value / children_total_potential
    grade_query = ProjectGrade.objects.filter(project=project).filter(grade_category=parent)
    give_automated_project_grade(amount, parent, project, grade_query)
    if grade_query.filter(grade_type="M").count() > 0:
        return
    propagate_grade_up(project, parent)


def pick_grade(query):
    options = query.all()
    order = ["M", "A", "P"]
    for target_type in order:
        for option in options:
            if option.grade_type == target_type:
                return option


def give_automated_project_grade(amount, grade_category, project, grades_query):
    give_automated_grade_general(amount, grade_category, project, grades_query, "project")


def give_automated_grade(amount, grade_category, user_project, grades_query):
    give_automated_grade_general(amount, grade_category, user_project, grades_query, "user")


def give_automated_grade_general(amount, grade_category, user, grades_query, grade_type):
    give_grade(grades_query, amount, grade_type, "A", user, grade_category)


def give_manual_grade(query, amount, grade_type, user, grade_category):
    give_grade(query, amount, grade_type, "M", user, grade_category)


def give_grade(query, amount, grading_type, grade_type, user, grade_category):
    added_data = False
    for old_grade in query.all():
        if old_grade.grade_type == "P":
            old_grade.delete()
        elif old_grade.grade_type == grade_type:
            old_grade.amount = amount
            old_grade.save()
            added_data = True
    if not added_data:
        if grading_type == "user":
            UserGrade.objects.create(amount=amount, user_project=user, grade_category=grade_category, grade_type=grade_type)
        else:
            ProjectGrade.objects.create(amount=amount, project=user, grade_category=grade_category, grade_type=grade_type)


def grade_user(user_id, grade_category, amount):
    user_project = UserProject.objects.filter(pk=user_id).first()
    search = UserGrade.objects.filter(user_project=user_project).filter(grade_category=grade_category)
    give_manual_grade(search, amount, "user", user_project, grade_category)
    propagate_grade_up(user_project, grade_category)


def grade_project(user_project_id, grade_category, amount):
    project = UserProject.objects.filter(pk=user_project_id).first().project
    search = ProjectGrade.objects.filter(project=project).filter(grade_category=grade_category)
    give_manual_grade(search, amount, "project", project, grade_category)
    propagate_grade_up(project, grade_category)


def grade(target_id, grade_id, amount):
    grade_category = GradeCategory.objects.filter(pk=grade_id).first()
    if grade_category.project_grade:
        grade_project(target_id, grade_category, amount)
    else:
        grade_user(target_id, grade_category, amount)


def get_child_grades(child_user_grades):
    child_grades = []
    for child_user_grade in child_user_grades:
        q1 = child_user_grade.filter(grade_type="M")
        if q1.count() == 0:
            q2 = child_user_grade.filter(grade_type="A")
            if q2.count() == 0:
                child_grades.append(0)
            else:
                child_grades.append(q2.first().amount)
        else:
            child_grades.append(q1.first().amount)
    return child_grades


def recalculate_smi(grade_category, children, child_user_grades, user, query, grade_give_function):
    func = GradeCategory.GRADE_TYPE_FUNCS[grade_category.grade_type]
    total_potential = func([child.total for child in children])
    child_grades = get_child_grades(child_user_grades)
    total_value = func(child_grades)
    amount = grade_category.total * total_value / total_potential
    grade_give_function(amount, grade_category, user, query)


def recalculate_project_grade(grade_category, project):
    children = grade_category.children.all()
    for child in children:
        recalculate_project_grade(child, project)

    if grade_category.grade_type in "SMI":
        child_user_grades = [ProjectGrade.objects.filter(grade_category=child).filter(project=project) for child in children]
        user_grade = ProjectGrade.objects.filter(grade_category=grade_category).filter(project=project).filter(grade_type="A")
        recalculate_smi(grade_category, children, child_user_grades, project, user_grade, give_automated_project_grade)
    elif grade_category.grade_type == "A":
        automation = AutomateGrade.objects.filter(grade_category=grade_category)
        if automation.count() == 0:
            return
        automation = automation.first()
        user_grade = ProjectGrade.objects.filter(grade_category=grade_category).filter(project=project).filter(grade_type="A")

        if automation.automation_type == "R":
            amount = random.random() * grade_category.total  # TODO: Think about if grade has already been rolled, should we roll it again
        elif automation.automation_type == "T":
            grade_milestone = model_traversal.get_grade_milestone_for_grade_category(grade_category)
            time_spent = get_time_spent_for_project_in_milestone(project, grade_milestone)
            amount = decimal.Decimal(min(1, time_spent / automation.amount_needed)) * grade_category.total
        elif automation.automation_type == "L":
            grade_milestone = model_traversal.get_grade_milestone_for_grade_category(grade_category)
            lines_added = get_lines_added_for_project_in_milestone(project, grade_milestone)
            amount = decimal.Decimal(min(1, lines_added / automation.amount_needed)) * grade_category.total
        give_automated_project_grade(amount, grade_category, project, user_grade)


def recalculate_user_grade(grade_category, user_project):
    children = grade_category.children.all()
    for child in children:
        if child.project_grade:
            recalculate_project_grade(child, user_project.project)
        else:
            recalculate_user_grade(child, user_project)

    if grade_category.grade_type in "SMI":
        child_user_grades = []
        for child in children:
            if child.project_grade:
                child_user_grades.append(ProjectGrade.objects.filter(grade_category=child).filter(project=user_project.project))
            else:
                child_user_grades.append(UserGrade.objects.filter(grade_category=child).filter(user_project=user_project))

        user_grade = UserGrade.objects.filter(grade_category=grade_category).filter(user_project=user_project).filter(grade_type="A")
        recalculate_smi(grade_category, children, child_user_grades, user_project, user_grade, give_automated_grade)
    elif grade_category.grade_type == "A":
        automation = AutomateGrade.objects.filter(grade_category=grade_category)
        if automation.count() == 0:
            return
        automation = automation.first()
        user_grade = UserGrade.objects.filter(grade_category=grade_category).filter(user_project=user_project).filter(grade_type="A")

        if automation.automation_type == "R":
            amount = random.random() * grade_category.total  # TODO: Think about if grade has already been rolled, should we roll it again
        elif automation.automation_type == "T":
            grade_milestone = model_traversal.get_grade_milestone_for_grade_category(grade_category)
            time_spent = get_time_spent_for_user_in_milestone(user_project, grade_milestone)
            amount = decimal.Decimal(min(1, time_spent / automation.amount_needed)) * grade_category.total
        elif automation.automation_type == "L":
            grade_milestone = model_traversal.get_grade_milestone_for_grade_category(grade_category)
            lines_added = get_lines_added_for_user_in_milestone(user_project, grade_milestone)
            amount = decimal.Decimal(min(1, lines_added / automation.amount_needed)) * grade_category.total
        give_automated_grade(amount, grade_category, user_project, user_grade)


def recalculate_grade_category(grade_category):
    if grade_category.project_grade:
        for project in set([project_grade.project for project_grade in ProjectGrade.objects.filter(grade_category=grade_category).all()]):
            recalculate_project_grade(grade_category, project)
    else:
        for user_project in set([user_grade.user_project for user_grade in UserGrade.objects.filter(grade_category=grade_category).all()]):
            recalculate_user_grade(grade_category, user_project)


def get_time_spent_for_project_in_milestone(project, grade_milestone):
    return sum([get_time_spent_for_user_in_milestone(user_project, grade_milestone) for user_project in UserProject.objects.filter(project=project).filter(disabled=False).all()])


def get_issue_data_for_user_in_milestone(user_project, grade_milestone):
    data = {}
    data["authored"] = Issue.objects\
        .filter(author=user_project.account)\
        .filter(milestone__grade_milestone=grade_milestone).count()
    data["closed"] = Issue.objects \
        .filter(closed_by=user_project.account) \
        .filter(milestone__grade_milestone=grade_milestone).count()
    data["participated"] = Issue.objects\
        .filter(timespent__user=user_project.account)\
        .filter(milestone__grade_milestone=grade_milestone).count()
    return data


def get_time_spent_for_user_in_milestone(user_project, grade_milestone):
    times_spent = TimeSpent.objects.filter(user=user_project.account).filter(issue__milestone__grade_milestone=grade_milestone).all()
    return sum([time_spend.amount for time_spend in times_spent if grade_milestone.start <= time_spend.time <= grade_milestone.end]) / 60


def get_lines_added_for_project_in_milestone(project, grade_milestone):
    return sum([get_lines_added_for_user_in_milestone(user_project, grade_milestone) for user_project in UserProject.objects.filter(project=project).filter(disabled=False).all()])


def get_lines_added_for_user_in_milestone(user_project, grade_milestone):
    project = user_project.project
    repos = Repository.objects.filter(project=project).all()
    commits = []
    for repo in repos:
        commits += [commit for commit in Commit.objects.filter(repository=repo).all() if grade_milestone.start <= commit.time <= grade_milestone.end]
    return sum([commit.lines_added for commit in commits])


def generate_grade_category_copy(grade_category, parent):
    new_category = GradeCategory.objects.create(
        name=grade_category.name,
        total=grade_category.total,
        grade_type=grade_category.grade_type,
        description=grade_category.description,
        project_grade=grade_category.project_grade,
        parent_category=parent
    )
    if new_category.grade_type == "A":
        old_automate_grade = AutomateGrade.objects.filter(grade_category=grade_category).first()
        AutomateGrade.objects.create(
            automation_type=old_automate_grade.automation_type,
            amount_needed=old_automate_grade.amount_needed,
            grade_category=new_category
        )
    gm_query = GradeMilestone.objects.filter(grade_category=grade_category)
    project_group = model_traversal.get_project_group_of_grade_category_id(grade_category.pk)
    if gm_query.count() > 0:
        gm = gm_query.first()

        amount = model_traversal.get_amount_of_grademilestone_by_projectgroup(project_group)
        GradeMilestone.objects.create(
            start=gm.start,
            end=gm.end,
            milestone_order_id=amount + 1,
            grade_category=new_category
        )
    add_grades_to_category(new_category, project_group)
    for child in grade_category.children.all():
        generate_grade_category_copy(child, new_category)
