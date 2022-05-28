
from .models import UserProjectGroup, UserProject


def user_has_access_to_project_group_with_security_level(user, project_group, roles):
    user_project_groups = UserProjectGroup.objects.filter(project_group=project_group).filter(account=user)
    for user_group in user_project_groups.all():
        if user_group.rights in roles:
            return True
    return False


def user_has_access_to_project_with_security_level(user, project, roles):
    user_projects = UserProject.objects.filter(project=project).filter(account=user)
    for user_project in user_projects.all():
        if user_project.rights in roles:
            return True
    return user_has_access_to_project_group_with_security_level(user, project.project_group, roles)


def user_has_access_to_project(user, project):
    user_projects = UserProject.objects.filter(project=project).filter(account=user)
    if user_projects.count() > 0:
        return True
    project_group = project.project_group
    return user_has_access_to_project_group_with_security_level(user, project_group, ["A", "O"])


def user_has_access_to_project_group_with_security_level_at_least(project_group, user, role):
    user_roles = [x.rights for x in UserProjectGroup.objects.filter(project_group=project_group).filter(account=user).all()]
    max_index = max([UserProjectGroup.role_hierarchy.index(x) for x in user_roles])
    target_index = UserProjectGroup.role_hierarchy.index(role)
    return max_index >= target_index


def user_has_access_to_project_group_with_security_level_more_than(project_group, user, role):
    user_roles = [x.rights for x in UserProjectGroup.objects.filter(project_group=project_group).filter(account=user).all()]
    max_index = max([UserProjectGroup.role_hierarchy.index(x) for x in user_roles])
    target_index = UserProjectGroup.role_hierarchy.index(role)
    return max_index > target_index

