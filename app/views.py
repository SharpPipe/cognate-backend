import decimal
import string

import requests
import random
import hashlib
import time
import threading

from rest_framework import views
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from .models import ProjectGroup, UserProjectGroup, Profile, Project, Repository, GradeCategory, GradeCalculation, \
    GradeMilestone, UserProject, UserGrade, Milestone, Issue, TimeSpent, AutomateGrade, Feedback, Process

from .serializers import ProjectGroupSerializer, ProjectSerializer, RepositorySerializer, GradeCategorySerializer, \
    RegisterSerializer, GradeCategorySerializerWithGrades, MilestoneSerializer, GradeMilestoneSerializer, \
    ProcessSerializer


def get_members_from_repo(repo, user, get_all):
    base_url = "https://gitlab.cs.ttu.ee"
    api_part = "/api/v4"
    endpoint_part = f"/projects/{repo.gitlab_id}/members" + ("/all" if get_all else "")
    token_part = f"?private_token={user.profile.gitlab_token}"
    print(token_part)

    answer = requests.get(base_url + api_part + endpoint_part + token_part)
    return answer.json()


def add_user_grade_recursive(user_project, category):
    UserGrade.objects.create(amount=0, user_project=user_project, grade_category=category)
    for child in category.children.all():
        add_user_grade_recursive(user_project, child)


def add_user_grade(user_project, project_group):
    root_category = project_group.grade_calculation.grade_category
    add_user_grade_recursive(user_project, root_category)


def get_root_category(category):
    if category.parent_category is not None:
        return get_root_category(category.parent_category)
    return category


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


def pick_user_grade(query):
    options = query.all()
    order = ["M", "A", "P"]
    for target_type in order:
        for option in options:
            if option.grade_type == target_type:
                return option


def grade_user(user_id, grade_id, amount):
    user_project = UserProject.objects.filter(pk=user_id).first()
    grade = GradeCategory.objects.filter(pk=grade_id).first()
    search = UserGrade.objects.filter(user_project=user_project).filter(grade_category=grade)

    added_data = False
    for old_grade in search.all():
        if old_grade.grade_type == "P":
            old_grade.delete()
        elif old_grade.grade_type == "M":
            old_grade.amount = amount
            old_grade.save()
            added_data = True
        elif old_grade.grade_type == "A":
            pass
    if not added_data:
        new_grade = UserGrade.objects.create(amount=amount, user_project=user_project,
                                             grade_category=grade, grade_type="M")

    parent = grade.parent_category
    while parent is not None:
        modify = False
        if parent.grade_type == "S":
            func = sum
            modify = True
        elif parent.grade_type == "M":
            func = max
            modify = True
        elif parent.grade_type == "I":
            func = min
            modify = True

        if modify:
            children = parent.children
            children_total_potential = func([c.total for c in children.all()])
            children_total_value = func(
                [pick_user_grade(UserGrade.objects.filter(user_project=user_project).filter(grade_category=c)).amount
                 for c in children.all()])

            # TODO: Refactor updating parent as well. For now lets agree to not manually overwrite sum, max or min type grades
            parent_grade = UserGrade.objects.filter(user_project=user_project).filter(grade_category=parent).first()
            parent_grade.amount = parent.total * children_total_value / children_total_potential
            parent_grade.save()
        else:
            break

        grade = parent
        parent = grade.parent_category


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


def update_repository(id, user, new_users):
    repo = Repository.objects.filter(pk=id).first()
    project = repo.project
    grade_category_root = project.project_group.grade_calculation.grade_category
    base_url = "https://gitlab.cs.ttu.ee"
    api_part = "/api/v4"
    token_part = f"?private_token={user.profile.gitlab_token}&per_page=100"

    # Refresh users
    answer_json = get_members_from_repo(repo, user, False)
    print(answer_json)
    user_objects = []
    for member in answer_json:
        print(member)
        if member["access_level"] >= 30:
            create_user(member['username'], user_objects)
        print(f"{member['username']}")
        print()
    for user_object in user_objects:
        if UserProject.objects.filter(account=user_object).filter(project=repo.project).count() == 0:
            user_project = UserProject.objects.create(rights="M", account=user_object, project=project)
            add_user_grade_recursive(user_project, grade_category_root)

    # Load all milestones
    endpoint_part = f"/projects/{repo.gitlab_id}/milestones"
    answer = requests.get(base_url + api_part + endpoint_part + token_part).json()
    print(answer)
    for milestone in answer:
        gitlab_id = milestone["id"]
        if repo.milestones.filter(gitlab_id=gitlab_id).count() == 0:
            Milestone.objects.create(repository=repo, title=milestone["title"], gitlab_id=milestone["id"])
            print(f"Created milestone {milestone['title']}")

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
    for issue in issues:
        gitlab_id = issue['id']
        gitlab_iid = issue['iid']
        title = issue['title']
        milestone = issue['milestone']
        issues_to_refresh.append((gitlab_iid, gitlab_id))
        issue_query = Issue.objects.filter(gitlab_id=gitlab_id)
        if issue_query.count() == 0:
            if milestone is not None:
                issue_object = Issue.objects.create(gitlab_id=gitlab_id, title=title, gitlab_iid=gitlab_iid, milestone=Milestone.objects.filter(gitlab_id=milestone['id']).first())
            else:
                issue_object = Issue.objects.create(gitlab_id=gitlab_id, title=title, gitlab_iid=gitlab_iid)
        else:
            issue_object = issue_query.first()
            if milestone is not None:
                milestone_object = Milestone.objects.filter(gitlab_id=milestone['id']).first()
                if issue_object.milestone != milestone_object:
                    if issue_object.milestone is None:
                        issue_object.has_been_moved = True
                    issue_object.milestone = milestone_object
                    issue_object.save()

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
                time_spent = TimeSpent.objects.create(gitlab_id=gitlab_id, amount=amount, time=created_at, issue=issue, user=user)
        else:
            print(f"Unknown message with content {body}")

    # Load all commits
    # TODO: Load commit data

    return repo


def get_grade_milestones_by_projectgroup(project_group):
    grademilestones = []
    for test_milestone in GradeMilestone.objects.all():
        root_category = test_milestone.grade_category
        while root_category.parent_category is not None:
            root_category = root_category.parent_category
        if project_group == GradeCalculation.objects.filter(grade_category=root_category).first().project_group:
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
        if project_group == GradeCalculation.objects.filter(grade_category=root_category).first().project_group:
            return test_milestone


def get_milestone_data_for_project(request, id, milestone_id):
    project = Project.objects.filter(pk=id).first()
    milestone = get_grademilestone_by_projectgroup_and_milestone_order_number(project.project_group, milestone_id)
    if milestone is None:
        return {"status": 418, "error": f"Milestone {milestone_id} not found for project {id}."}

    promised_json = []
    print(milestone)

    user_projects = UserProject.objects.filter(project=project).all()
    print(user_projects)
    for user_project in user_projects:
        print(user_project.account.username)
        user_list = []
        times_spent = TimeSpent.objects.filter(user=user_project.account).filter(
            issue__milestone__grade_milestone=milestone).all()
        print(f"User {user_project}")
        total_time = sum([time_spend.amount for time_spend in times_spent if milestone.start <= time_spend.time <= milestone.end]) / 60
        promised_json.append({
            "username": user_project.account.username,
            "id": user_project.pk,
            "spent_time": total_time,
            "data": user_list
        })
        for grade_category in GradeCategory.objects.filter(parent_category=milestone.grade_category).all():
            category_data = {}
            user_list.append(category_data)
            user_grades = UserGrade.objects.filter(grade_category=grade_category).filter(user_project=user_project)
            category_data["name"] = grade_category.name
            category_data["total"] = grade_category.total
            category_data["automatic_points"] = None
            category_data["given_points"] = None
            category_data["id"] = grade_category.pk

            if user_grades.filter(grade_type="A").count() == 0:
                automate_grade = AutomateGrade.objects.filter(grade_category=grade_category)
                if automate_grade.count() > 0:
                    automate_grade = automate_grade.first()
                    if automate_grade.automation_type == "T":
                        percent_done = min(1, total_time / automate_grade.amount_needed)
                        points = decimal.Decimal(percent_done) * grade_category.total
                        UserGrade.objects.create(grade_type="A", amount=points, user_project=user_project,
                                                 grade_category=grade_category)
                        user_grades.filter(grade_type="P").delete()

            for user_grade in user_grades.all():
                if user_grade.grade_type == "A":
                    category_data["automatic_points"] = user_grade.amount
            for user_grade in user_grades.all():
                if user_grade.grade_type == "M":
                    category_data["given_points"] = user_grade.amount

            print(grade_category.name)
        print()
    return {"status": 200, "project_name": project.name, "project_data": promised_json}


anonymous_json = {"Error": "Not logged in."}
no_access_json = {"Error": "You don't have access"}


def user_has_access_to_project_group_with_security_level(user, project_group, roles):
    user_project_groups = UserProjectGroup.objects.filter(project_group=project_group).filter(account=user)
    for user_group in user_project_groups.all():
        if user_group.rights in roles:
            return True
    return False


def user_has_access_to_project(user, project):
    user_projects = UserProject.objects.filter(project=project).filter(account=user)
    if user_projects.count() > 0:
        return True
    project_group = project.project_group
    return user_has_access_to_project_group_with_security_level(user, project_group, ["A", "O"])


def project_group_of_grade_category_id(grade_id):
    root_category = get_root_category(GradeCategory.objects.filter(id=grade_id).first())
    return root_category.grade_calculation.project_group


def update_all_repos_in_group(project_group, user, process):
    print(f"Starting process with hash {process.hash}")
    repos = []
    new_users = []
    for project in project_group.project_set.all():
        for repository in project.repository_set.all():
            repos.append(repository.pk)
    for i, repo in enumerate(repos):
        update_repository(repo, user, new_users)
        process.completion_percentage = 100 * i / len(repos)
        process.save()
        print(f"{100 * i / len(repos)}% done refreshing repos")
    process.completion_percentage = 100
    process.status = "F"
    process.data = ProjectGroupSerializer(project_group).data
    process.save()
    print(f"Added users {new_users}")
    print(f"Finished process with hash {process.hash}")


class ProjectGroupView(views.APIView):
    def get(self, request):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        queryset = ProjectGroup.objects.filter(user_project_groups__account=request.user)
        serializer = ProjectGroupSerializer(queryset, many=True)
        data = serializer.data
        for point in data:
            point["rights"] = [conn.rights for conn in UserProjectGroup.objects.filter(account=request.user).filter(project_group=point["id"]).all()]
        return JsonResponse(data, safe=False)

    def post(self, request):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        serializer = ProjectGroupSerializer(data=request.data)
        if serializer.is_valid():
            project_group = serializer.save()
            UserProjectGroup.objects.create(rights="O", account=request.user, project_group=project_group)
            grade_category = GradeCategory.objects.create(name="root", grade_type="S")
            grade_calculation = GradeCalculation.objects.create(grade_category=grade_category, project_group=project_group)
        return JsonResponse({})


class ProjectGroupLoadProjectsView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        # x8xkGpUazyPda_ecaGtG
        print(f"Getting projects for project group {id}")
        group = ProjectGroup.objects.filter(pk=id).first()
        if not user_has_access_to_project_group_with_security_level(request.user, group, ["A", "O"]):
            return JsonResponse(no_access_json)

        print(f"Project group is {group} with gitlab group id {group.group_id}")
        profile = Profile.objects.filter(user=request.user).first()
        print(f"User's provided auth token is {profile.gitlab_token}")

        base_url = "https://gitlab.cs.ttu.ee"
        api_part = "/api/v4"
        endpoint_part = f"/groups/{group.group_id}/projects"
        token_part = f"?private_token={profile.gitlab_token}&per_page=100"
        # TODO: Theoretically there is a chance that there are more than 100 projects per group

        answer = requests.get(base_url + api_part + endpoint_part + token_part)
        print(f"Got response")

        json = answer.json()
        if not isinstance(json, list):
            error = f"Something went wrong, expected 'json' variable to be a list, but was {type(json)} instead.\n"
            error += f"'json' value: {json}"
            print(error)
            return JsonResponse({"error": error})
        data = []
        print(json)
        for project in json:
            data.append({
                "name": project["name"],
                "id": project["id"],
                "url": project["web_url"]
            })
            if Repository.objects.filter(gitlab_id=project["id"]).count() > 0:
                continue
            project_object = Project.objects.create(name=project["name_with_namespace"], project_group=group)
            repo = Repository.objects.create(url=project["web_url"], gitlab_id=project["id"], name=project["name"], project=project_object)
            members = [member["username"] for member in get_members_from_repo(repo, request.user, True)]
            for user in User.objects.filter(username__in=members).all():
                rights_query = UserProjectGroup.objects.filter(account=user).filter(project_group=group)
                if rights_query.count() > 0 and rights_query.first().rights in ["A", "O"]:
                    continue
                user_project = UserProject.objects.create(rights="M", account=user, project=project_object)
                add_user_grade(user_project, group)

        return JsonResponse({"data": data})


class ProjectsView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        group = ProjectGroup.objects.filter(pk=id).first()
        if not user_has_access_to_project_group_with_security_level(request.user, group, ["A", "O", "V"]):
            return JsonResponse(no_access_json)
        projects = Project.objects.filter(project_group=group)
        serializer = ProjectSerializer(projects, many=True)
        return JsonResponse(serializer.data, safe=False)


class RepositoryView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        project = Project.objects.filter(pk=id).first()
        if not user_has_access_to_project(request.user, project):
            return JsonResponse(no_access_json)
        repos = Repository.objects.filter(project=project)
        serializer = RepositorySerializer(repos, many=True)
        return JsonResponse(serializer.data, safe=False)


class ProfileView(views.APIView):
    def put(self, request):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        profile = Profile.objects.filter(user=request.user).first()
        profile.gitlab_token = request.data["gitlab_token"]
        profile.save()
        return JsonResponse({})


class GradeCategoryView(views.APIView):
    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        serializer = GradeCategorySerializer(data=request.data)
        parent = GradeCategory.objects.filter(pk=id).first()

        # Validate that user has correct access rights
        root = parent
        while root.parent_category is not None:
            root = root.parent_category
        project_group = root.grade_calculation.project_group
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project_group)
        allowed_rights = ["A", "O"]
        print(user_project_groups.count())
        print(user_project_groups.first().rights)
        has_rights = user_project_groups.count() > 0 and user_project_groups.first().rights in allowed_rights

        print(serializer.is_valid())
        print(has_rights)
        if has_rights and serializer.is_valid():
            grade_category = serializer.save()
            grade_category.parent_category = parent
            grade_category.save()
            for project in project_group.project_set.all():
                for user_project in project.userproject_set.all():
                    add_user_grade_recursive(user_project, grade_category)
            if "start" in request.data.keys() and "end" in request.data.keys() and len(request.data["start"]) > 0 and len(request.data["end"]) > 0:
                amount = get_amount_of_grademilestone_by_projectgroup(project_group)
                grade_milestone = GradeMilestone.objects.create(
                    start=request.data["start"],
                    end=request.data["end"],
                    grade_category=grade_category,
                    milestone_order_id=amount + 1
                )
            return JsonResponse(GradeCategorySerializer(grade_category).data)
        return JsonResponse({4: 18})

    def delete(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        grade_category = GradeCategory.objects.filter(pk=id).first()
        root = grade_category
        while root.parent_category is not None:
            root = root.parent_category
        project_group = root.grade_calculation.project_group
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project_group)
        allowed_rights = ["O"]
        has_rights = user_project_groups.count() > 0 and user_project_groups.first().rights in allowed_rights
        if has_rights:
            try:
                target_milestone = grade_category.grademilestone
            except ObjectDoesNotExist:
                # Is not a milestone
                grade_category.delete()
                return JsonResponse({200: "OK"})
            else:
                all_milestones = get_grade_milestones_by_projectgroup(project_group)
                for milestone in all_milestones:
                    if milestone.milestone_order_id > target_milestone.milestone_order_id:
                        milestone.milestone_order_id = milestone.milestone_order_id - 1
                        milestone.save()
                target_milestone.delete()
                grade_category.delete()
                return JsonResponse({200: "OK"})
        return JsonResponse({4: 18})


class ProjectGroupGradingView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if not user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O", "V"]):
            return JsonResponse(no_access_json)
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project_group)
        if user_project_groups.count() == 0:
            return JsonResponse({4: 18})
        root_category = project_group.grade_calculation.grade_category
        print(root_category)
        return JsonResponse(GradeCategorySerializer(root_category).data)


class ProjectGradesView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        project = Project.objects.filter(pk=id).first()
        user_projects = UserProject.objects.filter(account=request.user).filter(project=project)
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project.project_group)
        if user_project_groups.count() == 0:
            # TODO: If user_projects has users, then the request came from student, he should see his own grades.
            return JsonResponse({4: 18})
        members = project.userproject_set
        project_group_admins = project.project_group.user_project_groups
        print(members)
        print(project_group_admins.count())
        print(project.project_group)

        project_group = project.project_group
        root_category = project_group.grade_calculation.grade_category
        print(root_category)

        users = [user_project.id for user_project in UserProject.objects.filter(project=project).all()]
        print(users)

        return JsonResponse(GradeCategorySerializerWithGrades(root_category, context={"user_projects": users}).data)


class RootAddUsers(views.APIView):
    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        if not request.user.is_superuser:
            return JsonResponse(no_access_json)

        users = request.data["data"]
        user_objects = []
        for user in users:
            create_user(user, user_objects)

        project_group = ProjectGroup.objects.filter(pk=id).first()
        print(project_group)
        projects = Project.objects.filter(project_group=project_group)
        print(projects)
        grade_category_root = project_group.grade_calculation.grade_category
        for project in projects:
            users_found = []
            for repo in project.repository_set.all():
                answer_json = get_members_from_repo(repo, request.user, False)
                print(answer_json)
                for member in answer_json:
                    for user in user_objects:
                        if user.username in users_found:
                            continue
                        if member["username"] == user.username:
                            if UserProject.objects.filter(account=user).filter(project=project).count() == 0:
                                user_project = UserProject.objects.create(rights="M", account=user, project=project)
                                add_user_grade_recursive(user_project, grade_category_root)
                                users_found.append(user.username)
                                print(f"{member['username']} found in project {project.name}")
        return JsonResponse({200: "OK"})


class MockAccounts(views.APIView):
    def get(self, request):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        if not request.user.is_superuser:
            return JsonResponse(no_access_json)
        accounts = User.objects.filter(profile__actual_account=False)
        return JsonResponse([x.id for x in accounts], safe=False)


class GradeUserView(views.APIView):
    def post(self, request, user_id, grade_id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        project_group = project_group_of_grade_category_id(grade_id)
        if not user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
            return JsonResponse(no_access_json)
        print(f"Grading user {user_id} and grade {grade_id} with data {request.data}")
        grade_user(user_id, grade_id, request.data["amount"])
        return JsonResponse({200: "OK"})


class RepositoryUpdateView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        if not user_has_access_to_project(request.user, Repository.objects.filter(pk=id).first().project):
            return JsonResponse(no_access_json)
        repo = update_repository(id, request.user, [])
        return JsonResponse({200: "OK", "data": RepositorySerializer(repo).data})


class ProjectGroupUpdateView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if not user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
            return JsonResponse(no_access_json)
        h = hashlib.sha256()
        [h.update(str(x).encode()) for x in [time.time(), id, request.user.pk]]
        process = Process.objects.create(hash=h.hexdigest(), type="SG", status="O", completion_percentage=0)
        process.save()
        t = threading.Thread(target=update_all_repos_in_group, args=[project_group, request.user, process], daemon=True)
        t.start()
        return JsonResponse({
            "id": process.pk,
            "hash": process.hash
        })


class ProjectMilestonesView(views.APIView):
    def get(self, request, id):
        # TODO: repurpose this endpoint
        print(request.user)
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        if not user_has_access_to_project(request.user, Project.objects.filter(id=id).first()):
            return JsonResponse(no_access_json)
        data = []
        i = 1
        name = ""
        while True:
            res = get_milestone_data_for_project(request, id, i)
            if res["status"] == 418:
                break
            name = res["project_name"]
            data.append({"milestone_number": i, "milestone_data": res["project_data"]})
            i += 1
        return JsonResponse({"status": 200, "project_name": name, "project_data": data})


class GroupSummaryMilestoneDataView(views.APIView):
    def get(self, request, id, milestone_id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        data = []
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if not user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
            return JsonResponse(no_access_json)
        for project in project_group.project_set.all():
            project_res = get_milestone_data_for_project(request, project.pk, milestone_id)
            if project_res["status"] == 418:
                return JsonResponse(project_res)
            del project_res["status"]
            data.append(project_res)
        return JsonResponse({200: "OK", "data": data})


class ProjectMilestoneDataView(views.APIView):
    def get(self, request, id, milestone_id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        if not user_has_access_to_project(request.user, Project.objects.filter(pk=id).first()):
            return JsonResponse(no_access_json)
        res = get_milestone_data_for_project(request, id, milestone_id)
        if res["status"] == 418:
            return JsonResponse(res)
        del res["status"]
        return JsonResponse({200: "OK", "data": res})


class ProjectMilestoneTimeSpentView(views.APIView):
    def get(self, request, id, milestone_id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        project = Project.objects.filter(pk=id).first()
        if not user_has_access_to_project(request.user, project):
            return JsonResponse(no_access_json)
        milestone = get_grademilestone_by_projectgroup_and_milestone_order_number(project.project_group, milestone_id)
        if milestone is None:
            return JsonResponse({"status": 418, "error": f"Milestone {milestone_id} not found for project {id}."})

        promised_json = []

        user_projects = UserProject.objects.filter(project=project).all()
        for user_project in user_projects:
            times_spent = TimeSpent.objects.filter(user=user_project.account).filter(issue__milestone__grade_milestone=milestone).all()
            for time_spent in times_spent:
                promised_json.append({
                    "datetime": time_spent.time,
                    "author": time_spent.user.username,
                    "amount": time_spent.amount,
                    "subject": time_spent.issue.title
                })
        return JsonResponse(promised_json, safe=False)


class BulkGradeView(views.APIView):
    def post(self, request):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        print(request.data)
        checked = False

        for sub_grade in request.data:
            if not checked:
                project_group = project_group_of_grade_category_id(sub_grade["grade_id"])
                if not user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
                    return JsonResponse(no_access_json)
                checked = True
            grade_user(sub_grade["user_group_id"], sub_grade["grade_id"], sub_grade["points"])
        return JsonResponse({200: "OK"})


class FeedbackView(views.APIView):
    def post(self, request):
        Feedback.objects.create(text=request.data["feedback"])
        return JsonResponse({200: "OK"})


class ProjectMilestoneConnectionsView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        project = Project.objects.filter(pk=id).first()
        if not user_has_access_to_project(request.user, project):
            return JsonResponse(no_access_json)

        # Grade milestones
        grade_milestones = get_grade_milestones_by_projectgroup(project.project_group)
        gm_serializer = GradeMilestoneSerializer(grade_milestones, many=True)

        # Repository milestones
        milestones = []
        for repository in project.repository_set.all():
            for milestone in repository.milestones.all():
                milestones.append(milestone)
        m_serializer = MilestoneSerializer(milestones, many=True)

        return JsonResponse({
            "grade_milestones": list(sorted(gm_serializer.data, key=lambda x: x["milestone_order_id"])),
            "milestones": m_serializer.data
        })


class MilestoneSetGradeMilestoneView(views.APIView):
    def put(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(anonymous_json)
        repo_milestone = Milestone.objects.filter(pk=id).first()
        if not user_has_access_to_project(request.user, repo_milestone.repository.project):
            return JsonResponse(no_access_json)
        if request.data["id"] != -1:
            grade_milestone = GradeMilestone.objects.filter(pk=request.data["id"]).first()
        else:
            grade_milestone = None
        # TODO: Check that connection is allowed
        if grade_milestone is not None:
            repo_milestone_project_group = repo_milestone.repository.project.project_group
            root_category = get_root_category(grade_milestone.grade_category)
            grade_milestone_project_group = GradeCalculation.objects.filter(grade_category=root_category).first().project_group
            if repo_milestone_project_group != grade_milestone_project_group:
                print(f"Repository milestone {repo_milestone} and grade milestone {grade_milestone} do not have matching project groups.")
                return JsonResponse({418: "ERROR"})

        repo_milestone.grade_milestone = grade_milestone
        repo_milestone.save()
        return JsonResponse({200: "OK"})


class TestLoginView(views.APIView):
    def get(self, request):
        if request.user.is_anonymous:
            return JsonResponse({}, status=401)
        return JsonResponse({})


class ProcessInfoView(views.APIView):
    def get(self, request, id, hash):
        if request.user.is_anonymous:
            return JsonResponse({}, status=401)
        processes = Process.objects.filter(pk=id).filter(hash=hash)
        if processes.count() == 0:
            return JsonResponse({"error": f"Process with id {id} and hash {hash} does not exist."}, status=404)
        return JsonResponse({"process": ProcessSerializer(processes.first()).data})
