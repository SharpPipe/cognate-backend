
from django.core.exceptions import ObjectDoesNotExist

from .models import AssessmentMilestone, AssessmentCalculation, AssessmentCategory


def get_assessment_milestone_for_assessment_category(assessment_category):
    if assessment_category is None:
        return
    try:
        return assessment_category.assessment_milestone
    except ObjectDoesNotExist:
        return get_assessment_milestone_for_assessment_category(assessment_category.parent_category)


def get_assessment_milestones_by_projectgroup(project_group):
    assessmentmilestones = []
    root_category = project_group.assessment_calculation.assessment_category
    get_assessment_milestones_from_assessment_category(root_category, assessmentmilestones)
    return assessmentmilestones


def get_assessment_milestones_from_assessment_category(assessment_category, assessment_milestones):
    try:
        assessment_milestones.append(assessment_category.assessment_milestone)
        return
    except ObjectDoesNotExist:
        pass
    for child in assessment_category.children.all():
        get_assessment_milestones_from_assessment_category(child, assessment_milestones)


def get_amount_of_assessmentmilestone_by_projectgroup(project_group):
    return len(get_assessment_milestones_by_projectgroup(project_group))


def get_assessmentmilestone_by_projectgroup_and_milestone_order_number(project_group, milestone_id):
    for test_milestone in AssessmentMilestone.objects.all():
        if test_milestone.milestone_order_id != milestone_id:
            continue
        root_category = test_milestone.assessment_category
        while root_category.parent_category is not None:
            root_category = root_category.parent_category
        query = AssessmentCalculation.objects.filter(assessment_category=root_category)
        if query.count() == 0:
            continue
        if project_group == query.first().project_group:
            return test_milestone


def get_project_group_of_assessment_category_id(assessment_id):
    root_category = get_root_category(AssessmentCategory.objects.filter(id=assessment_id).first())
    return root_category.assessment_calculation.project_group


def get_root_category(category):
    if category.parent_category is not None:
        return get_root_category(category.parent_category)
    return category


def get_project_from_milestone(milestone):
    if milestone.repository is None:
        return milestone.project
    return milestone.repository.project
