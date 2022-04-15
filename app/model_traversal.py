from django.core.exceptions import ObjectDoesNotExist

from .models import GradeMilestone, GradeCalculation, GradeCategory


def get_grade_milestone_for_grade_category(grade_category):
    if grade_category is None:
        return
    try:
        return grade_category.grademilestone
    except ObjectDoesNotExist:
        return get_grade_milestone_for_grade_category(grade_category.parent_category)


def get_grade_milestones_by_projectgroup(project_group):
    grademilestones = []
    for test_milestone in GradeMilestone.objects.all():
        root_category = test_milestone.grade_category
        while root_category.parent_category is not None:
            root_category = root_category.parent_category
        query = GradeCalculation.objects.filter(grade_category=root_category)
        if query.count() == 0:
            continue
        if project_group == query.first().project_group:
            grademilestones.append(test_milestone)
    return grademilestones


def get_amount_of_grademilestone_by_projectgroup(project_group):
    return len(get_grade_milestones_by_projectgroup(project_group))


def get_grademilestone_by_projectgroup_and_milestone_order_number(project_group, milestone_id):
    for test_milestone in GradeMilestone.objects.all():
        if test_milestone.milestone_order_id != milestone_id:
            continue
        root_category = test_milestone.grade_category
        while root_category.parent_category is not None:
            root_category = root_category.parent_category
        query = GradeCalculation.objects.filter(grade_category=root_category)
        if query.count() == 0:
            continue
        if project_group == query.first().project_group:
            return test_milestone


def get_project_group_of_grade_category_id(grade_id):
    root_category = get_root_category(GradeCategory.objects.filter(id=grade_id).first())
    return root_category.grade_calculation.project_group


def get_root_category(category):
    if category.parent_category is not None:
        return get_root_category(category.parent_category)
    return category
