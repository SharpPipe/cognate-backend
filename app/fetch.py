import gitlab
from .models import GitlabGroup

token = 'Wqy_ErqLwuwouxWzo2Bf'
url = 'https://gitlab.cs.ttu.ee'
gl = gitlab.Gitlab(url, private_token=token)


def fetch_groups():
    group = gl.groups.get(5008)
    repos = group.projects.list()
    name = group.full_name
    description = group.description
    id = group.get_id()
    gg = GitlabGroup(group_name=name, description=description, gitlab_id=id)
    gg.save()
    return gg


