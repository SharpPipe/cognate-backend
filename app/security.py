from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import base64
import os

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


def encrypt_token(user, password):
    if user.profile.gitlab_token_encrypted or user.profile.gitlab_token is None:
        return
    password = password.encode()
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    fernet = Fernet(key)
    token = fernet.encrypt(user.profile.gitlab_token.encode())

    user.profile.gitlab_token = token.hex()
    user.profile.gitlab_token_salt = salt.hex()
    user.profile.gitlab_token_encrypted = True
    user.profile.save()


def get_user_token(user, password):
    if user.profile.gitlab_token is None:
        return None
    if not user.profile.gitlab_token_encrypted:
        return user.profile.gitlab_token
    password = password.encode()
    raw_token = bytes.fromhex(user.profile.gitlab_token)
    salt = bytes.fromhex(user.profile.gitlab_token_salt)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    fernet = Fernet(key)
    token = fernet.decrypt(raw_token)
    return token.decode()
