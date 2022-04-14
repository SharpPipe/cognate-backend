
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