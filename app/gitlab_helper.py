import requests
import random
import string
import time
import datetime

from .models import User, Profile, Repository, UserProject, Milestone, Issue, TimeSpent, Commit, Committer

from .serializers import RegisterSerializer, ProjectGroupSerializer

from . import assessment_tree
from . import helpers


def get_token(repo, user, user_token):
    if repo.project.project_group.gitlab_token is not None:
        return repo.project.project_group.gitlab_token
    return user_token


def get_members_from_repo(repo, user, get_all, user_token):
    base_url = "https://gitlab.cs.ttu.ee"
    api_part = "/api/v4"
    endpoint_part = f"/projects/{repo.gitlab_id}/members" + ("/all" if get_all else "")
    token_part = f"?private_token={get_token(repo, user, user_token)}"
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


def update_all_repos_in_group(project_group, user, process, user_token):
    print(f"Starting process with hash {process.hash}")
    repos = []
    new_users = []
    for project in project_group.project_set.all():
        for repository in project.repository_set.all():
            repos.append(repository.pk)
    for i, repo in enumerate(repos):
        update_repository(repo, user, new_users, user_token)
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
    if total == done:
        process.status = "F"
        process.data = data
    process.save()


def update_repository(id, user, new_users, user_token, process=None):
    repo = Repository.objects.filter(pk=id).first()
    project = repo.project
    assessment_category_root = project.project_group.assessment_calculation.assessment_category
    base_url = "https://gitlab.cs.ttu.ee"
    api_part = "/api/v4"
    token_part = f"?private_token={get_token(repo, user, user_token)}&per_page=100"

    times = []

    # Refresh users
    times.append(time.time())  # 0
    answer_json = get_members_from_repo(repo, user, False, user_token)
    if process is not None: update_process(process, 1, 10)
    user_objects = []
    if not isinstance(answer_json, list):
        print()
        print("Error parsing response from get members")
        print(f"Repo {repo.pk}")
        print(f"Response was: {answer_json}")
        print("Expected list")
        print()
        return repo
    times.append(time.time())  # 1
    for member in answer_json:
        if member["access_level"] >= 30:
            create_user(member['username'], user_objects)
    if process is not None: update_process(process, 2, 10)
    times.append(time.time())  # 2
    for user_object in user_objects:
        if UserProject.objects.filter(account=user_object).filter(project=repo.project).count() == 0:
            user_project = UserProject.objects.create(rights="M", account=user_object, project=project, colour=helpers.random_colour())
            assessment_tree.add_user_assessment_recursive(user_project, assessment_category_root)
    times.append(time.time())  # 3
    if process is not None: update_process(process, 3, 10)

    # Load all milestones
    endpoint_part = f"/projects/{repo.gitlab_id}/milestones"
    answer = requests.get(base_url + api_part + endpoint_part + token_part).json()
    times.append(time.time())  # 4
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
    times.append(time.time())  # 5
    if process is not None: update_process(process, 4, 10)
    print("Here")
    endpoint_part = f"/projects/{repo.gitlab_id}"
    answer = requests.get(base_url + api_part + endpoint_part + token_part).json()
    times.append(time.time())  # 6
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
    times.append(time.time())  # 7

    # Load all issues
    issues = []
    endpoint_part = f"/projects/{repo.gitlab_id}/issues"
    counter = 1
    issues_to_refresh = []
    while True:
        answer = requests.get(base_url + api_part + endpoint_part + token_part + "&updated_after=" + repo.last_issue_sync.isoformat() + "&page=" + str(counter)).json()
        issues += answer
        if len(answer) < 100:
            break
        counter += 1
    repo.last_issue_sync = datetime.datetime.now()
    repo.save()
    times.append(time.time())  # 8
    if process is not None: update_process(process, 5, 10)
    for issue in issues:
        gitlab_id = issue['id']
        gitlab_iid = issue['iid']
        title = issue['title']
        milestone = issue['milestone']
        url = issue["web_url"]
        closed_by = issue["closed_by"]
        author = issue["author"]
        assignee = issue["assignee"]

        issues_to_refresh.append((gitlab_iid, gitlab_id))
        issue_query = Issue.objects.filter(gitlab_id=gitlab_id)
        issue_object = Issue.objects.create(gitlab_id=gitlab_id, gitlab_iid=gitlab_iid) if issue_query.count() == 0 else issue_query.first()

        if milestone is not None:
            milestone_object = Milestone.objects.filter(gitlab_id=milestone['id']).first()
            if issue_object.milestone != milestone_object:
                issue_object.has_been_moved = True
            issue_object.milestone = milestone_object

        if title is not None:
            issue_object.title = title
        if url is not None:
            issue_object.gitlab_link = url
        issue_object.repository = repo
        if closed_by is not None:
            issue_object.closed_by = User.objects.filter(username=closed_by["username"]).first()
        if author is not None:
            issue_object.author = User.objects.filter(username=author["username"]).first()
        if assignee is not None:
            issue_object.assignee = User.objects.filter(username=assignee["username"]).first()
        issue_object.save()
    times.append(time.time())  # 9

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
    times.append(time.time())  # 10
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
    times.append(time.time())  # 11
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
    times.append(time.time())  # 12
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
    times.append(time.time())  # 13
    if process is not None: update_process(process, 10, 10)
    for i in range(len(times) - 1):
        print(f"{i}: {times[i + 1] - times[i]}")
    return repo
