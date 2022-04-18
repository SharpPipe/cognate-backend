import requests
import random
import string

from .models import User, Profile, Repository, UserProject, Milestone, Issue, TimeSpent, Commit, Committer

from .serializers import RegisterSerializer, ProjectGroupSerializer

from . import grading_tree
from . import helpers


def get_token(repo, user):
    if repo.project.project_group.gitlab_token is not None:
        return repo.project.project_group.gitlab_token
    return user.profile.gitlab_token


def get_members_from_repo(repo, user, get_all):
    base_url = "https://gitlab.cs.ttu.ee"
    api_part = "/api/v4"
    endpoint_part = f"/projects/{repo.gitlab_id}/members" + ("/all" if get_all else "")
    token_part = f"?private_token={get_token(repo, user)}"
    print(token_part)
    answer = requests.get(base_url + api_part + endpoint_part + token_part)
    return answer.json()


def create_user(username, user_objects):
    users = User.objects.filter(username=username)
    if users.count() > 0:
        user_objects.append(users.first())
        return
    email = username + "@ttu.ee"
    sub_data = {}
    sub_data["username"] = username
    sub_data["email"] = email
    sub_data["password"] = "".join([random.choice(string.ascii_lowercase) for _ in range(20)])
    sub_data["password_confirm"] = sub_data["password"]
    if "." in username:
        sub_data["first_name"] = username.split(".")[0]
        sub_data["last_name"] = ".".join(username.split(".")[1:])
    else:
        sub_data["first_name"] = username[:len(username) // 2]
        sub_data["last_name"] = username[len(username) // 2:]
    serializer = RegisterSerializer(data=sub_data)
    serializer.is_valid()
    user_object = serializer.save()
    Profile.objects.create(user=user_object, actual_account=False)
    user_objects.append(user_object)


available_times = {
    "m": 1,
    "h": 60,
    "d": 480,
    "w": 2400
}


def minute_amount(message):
    at_numbers = True
    number_part = ''
    letter_part = ''
    for letter in message:
        if letter.isdigit():
            if not at_numbers:
                return False
            number_part += letter
        else:
            at_numbers = False
            letter_part += letter
    if len(number_part) == 0 or len(number_part) == 0:
        return False
    number = int(number_part)
    if letter_part not in available_times.keys():
        return False
    return number * available_times[letter_part]


def is_time_spent_message(message):
    if "added " not in message:
        return False, 0
    message = message.split("added ")[1]
    if " of time spent" not in message:
        return False, 0
    message = message.split(" of time spent")[0]
    parts = [minute_amount(x) for x in message.split(" ")]
    if False in parts:
        return False, 0
    return True, sum(parts)


def update_all_repos_in_group(project_group, user, process):
    print(f"Starting process with hash {process.hash}")
    repos = []
    new_users = []
    for project in project_group.project_set.all():
        for repository in project.repository_set.all():
            repos.append(repository.pk)
    for i, repo in enumerate(repos):
        update_repository(repo, user, new_users)
        process.completion_percentage = 100 * (i + 1) / len(repos)
        process.save()
        print(f"{100 * (i + 1) / len(repos)}% done refreshing repos")
    process.completion_percentage = 100
    process.status = "F"
    process.data = ProjectGroupSerializer(project_group).data
    process.save()
    print(f"Added users {new_users}")
    print(f"Finished process with hash {process.hash}")


def update_process(process, done, total, data=""):
    process.completion_percentage = done / total
    if process == done:
        process.status = "F"
        process.data = data
    process.save()


def update_repository(id, user, new_users, process=None):
    repo = Repository.objects.filter(pk=id).first()
    project = repo.project
    grade_category_root = project.project_group.grade_calculation.grade_category
    base_url = "https://gitlab.cs.ttu.ee"
    api_part = "/api/v4"
    token_part = f"?private_token={get_token(repo, user)}&per_page=100"

    # Refresh users
    answer_json = get_members_from_repo(repo, user, False)
    if process is not None: update_process(process, 1, 10)
    user_objects = []
    for member in answer_json:
        if member["access_level"] >= 30:
            create_user(member['username'], user_objects)
    if process is not None: update_process(process, 2, 10)
    for user_object in user_objects:
        if UserProject.objects.filter(account=user_object).filter(project=repo.project).count() == 0:
            user_project = UserProject.objects.create(rights="M", account=user_object, project=project, colour=helpers.random_colour())
            grading_tree.add_user_grade_recursive(user_project, grade_category_root)
    if process is not None: update_process(process, 3, 10)

    # Load all milestones
    endpoint_part = f"/projects/{repo.gitlab_id}/milestones"
    answer = requests.get(base_url + api_part + endpoint_part + token_part).json()
    for milestone in answer:
        gitlab_id = milestone["id"]
        matching = repo.milestones.filter(gitlab_id=gitlab_id)
        if matching.count() == 0:
            Milestone.objects.create(repository=repo, title=milestone["title"], gitlab_id=milestone["id"], gitlab_link=milestone["web_url"])
        elif matching.count() == 1:
            milestone_object = matching.first()
            # TODO: Maybe record the changes somehow?
            milestone_object.title = milestone["title"]
            milestone_object.gitlab_link = milestone["web_url"]
            milestone_object.save()
    if process is not None: update_process(process, 4, 10)
    print("Here")
    endpoint_part = f"/projects/{repo.gitlab_id}"
    answer = requests.get(base_url + api_part + endpoint_part + token_part).json()
    if answer["namespace"]["kind"] == "group":
        print("GROUP")
        endpoint_part = f"/groups/{answer['namespace']['id']}/milestones"
        answer = requests.get(base_url + api_part + endpoint_part + token_part).json()
        for milestone in answer:
            gitlab_id = milestone["id"]
            matching = repo.milestones.filter(gitlab_id=gitlab_id)
            if matching.count() == 0:
                Milestone.objects.create(project=repo.project, title=milestone["title"], gitlab_id=milestone["id"], gitlab_link=milestone["web_url"])
            elif matching.count() == 1:
                milestone_object = matching.first()
                # TODO: Maybe record the changes somehow?
                milestone_object.title = milestone["title"]
                milestone_object.gitlab_link = milestone["web_url"]
                milestone_object.save()
    print("Done")

    # Load all issues
    issues = []
    endpoint_part = f"/projects/{repo.gitlab_id}/issues"
    counter = 1
    issues_to_refresh = []
    while True:
        answer = requests.get(base_url + api_part + endpoint_part + token_part + "&page=" + str(counter)).json()
        issues += answer
        if len(answer) < 100:
            break
        counter += 1
    if process is not None: update_process(process, 5, 10)
    for issue in issues:
        gitlab_id = issue['id']
        gitlab_iid = issue['iid']
        title = issue['title']
        milestone = issue['milestone']
        url = issue["web_url"]
        issues_to_refresh.append((gitlab_iid, gitlab_id))
        issue_query = Issue.objects.filter(gitlab_id=gitlab_id)
        if issue_query.count() == 0:
            if milestone is not None:
                Issue.objects.create(gitlab_id=gitlab_id, title=title, gitlab_iid=gitlab_iid, gitlab_link=url, milestone=Milestone.objects.filter(gitlab_id=milestone['id']).first())
            else:
                Issue.objects.create(gitlab_id=gitlab_id, title=title, gitlab_iid=gitlab_iid, gitlab_link=url)
        else:
            issue_object = issue_query.first()
            to_save = False
            if issue_object.gitlab_link is None:
                issue_object.gitlab_link = url
                to_save = True
            if milestone is not None:
                milestone_object = Milestone.objects.filter(gitlab_id=milestone['id']).first()
                if issue_object.milestone != milestone_object:
                    if issue_object.milestone is None:
                        issue_object.has_been_moved = True
                    issue_object.milestone = milestone_object
                    to_save = True
            if to_save:
                issue_object.save()
    if process is not None: update_process(process, 6, 10)

    # Load all time spent
    time_spents = []

    for issue, id in issues_to_refresh:
        endpoint_part = f"/projects/{repo.gitlab_id}/issues/{issue}/notes"
        counter = 1
        while True:
            url = base_url + api_part + endpoint_part + token_part + "&page=" + str(counter)
            answer = requests.get(url).json()
            time_spents += [(id, x) for x in answer]
            if len(answer) < 100:
                break
            counter += 1
    if process is not None: update_process(process, 7, 10)
    for id, note in time_spents:
        body = note['body']
        author = note['author']['username']
        is_time_spent, amount = is_time_spent_message(body)
        gitlab_id = note['id']
        if is_time_spent:
            user = User.objects.filter(username=author)
            if user.count() == 0:
                print(f"Error, unknown user {author} logged time, repo id {repo.gitlab_id}")
                if author not in new_users:
                    new_users.append(author)
                continue
            if TimeSpent.objects.filter(gitlab_id=gitlab_id).count() == 0:
                user = user.first()
                created_at = note['created_at']
                issue = Issue.objects.filter(gitlab_id=id).first()
                TimeSpent.objects.create(gitlab_id=gitlab_id, amount=amount, time=created_at, issue=issue, user=user)
        else:
            pass
    if process is not None: update_process(process, 8, 10)

    # Load all commits
    # TODO: Load commit data
    print("Should load commits")
    endpoint_part = f"/projects/{repo.gitlab_id}/repository/commits"
    counter = 1
    commits = []
    while True:
        answer = requests.get(base_url + api_part + endpoint_part + token_part + "&with_stats=true&page=" + str(counter)).json()
        commits += answer
        if len(answer) < 100:
            break
        counter += 1
    if process is not None: update_process(process, 9, 10)
    for commit in commits:
        commit_hash = commit["id"]
        if Commit.objects.filter(hash=commit_hash).count() > 0:
            continue
        commit_time = commit["created_at"]
        message = commit["message"]
        lines_added = commit["stats"]["additions"]
        lines_removed = commit["stats"]["deletions"]
        name = commit["committer_name"]
        email = commit["committer_email"]
        committers = Committer.objects.filter(name=name).filter(email=email)
        if committers.count() > 0:
            committer = committers.first()
        else:
            committer = Committer.objects.create(name=name, email=email)
            users = User.objects.filter(username=name)
            if users.count() > 0:
                committer.account = users.first()
                committer.save()
            if "@" in email:
                users = User.objects.filter(username=email.split("@")[0])
                if users.count() > 0:
                    committer.account = users.first()
                    committer.save()
        Commit.objects.create(hash=commit_hash, time=commit_time, message=message, lines_added=lines_added, lines_removed=lines_removed, author=committer, repository=repo)
        print(commit)
    if process is not None: update_process(process, 10, 10)
    return repo
