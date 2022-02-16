import string

import requests
import random

from rest_framework import views
from django.http import JsonResponse
from django.contrib.auth.models import User

from .models import ProjectGroup, UserProjectGroup, Profile, Project, Repository, GradeCategory, GradeCalculation, \
    GradeMilestone, UserProject, UserGrade, Milestone, Issue, IssueMilestone, TimeSpent
from .serializers import ProjectGroupSerializer, ProjectSerializer, RepositorySerializer, GradeCategorySerializer, \
    RegisterSerializer, GradeCategorySerializerWithGrades


def get_members_from_repo(repo, user):
    base_url = "https://gitlab.cs.ttu.ee"
    api_part = "/api/v4"
    endpoint_part = f"/projects/{repo.gitlab_id}/members/all"
    token_part = f"?private_token={user.profile.gitlab_token}"

    answer = requests.get(base_url + api_part + endpoint_part + token_part)
    return answer.json()


def add_user_grade_recursive(user_project, category):
    UserGrade.objects.create(amount=0, user_project=user_project, grade_component=category)
    for child in category.children.all():
        add_user_grade_recursive(user_project, child)


def add_user_grade(user_project, project_group):
    root_category = project_group.grade_calculation.grade_category
    add_user_grade_recursive(user_project, root_category)


class ProjectGroupView(views.APIView):
    def get(self, request):
        queryset = ProjectGroup.objects.filter(user_project_groups__account=request.user)
        serializer = ProjectGroupSerializer(queryset, many=True)
        return JsonResponse(serializer.data, safe=False)

    def post(self, request):
        serializer = ProjectGroupSerializer(data=request.data)
        if serializer.is_valid():
            project_group = serializer.save()
            UserProjectGroup.objects.create(rights="O", account=request.user, project_group=project_group)
            grade_category = GradeCategory.objects.create(name="root", grade_type="S")
            grade_calculation = GradeCalculation.objects.create(grade_category=grade_category, project_group=project_group)
        return JsonResponse({})


class ProjectGroupLoadProjectsView(views.APIView):
    def get(self, request, id):
        # x8xkGpUazyPda_ecaGtG
        print(f"Getting projects for project group {id}")
        group = ProjectGroup.objects.filter(pk=id).first()
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
            if Project.objects.filter(gitlab_id=project["id"]).count() > 0:
                continue
            project_object = Project.objects.create(gitlab_id=project["id"], name=project["name_with_namespace"], project_group=group)
            repo = Repository.objects.create(url=project["web_url"], gitlab_id=project["id"], name=project["name"], project=project_object)
            members = [member["username"] for member in get_members_from_repo(repo, request.user)]
            for user in User.objects.filter(username__in=members).all():
                user_project = UserProject.objects.create(rights="M", account=user, project=project_object)
                add_user_grade(user_project, group)

        return JsonResponse({"data": data})


class ProjectsView(views.APIView):
    def get(self, request, id):
        group = ProjectGroup.objects.filter(pk=id).first()
        projects = Project.objects.filter(project_group=group)
        serializer = ProjectSerializer(projects, many=True)
        return JsonResponse(serializer.data, safe=False)


class RepositoryView(views.APIView):
    def get(self, request, id):
        project = Project.objects.filter(pk=id).first()
        repos = Repository.objects.filter(project=project)
        serializer = RepositorySerializer(repos, many=True)
        return JsonResponse(serializer.data, safe=False)


class ProfileView(views.APIView):
    def put(self, request):
        profile = Profile.objects.filter(user=request.user).first()
        profile.gitlab_token = request.data["gitlab_token"]
        profile.save()
        return JsonResponse({})


class GradeCategoryView(views.APIView):
    def post(self, request, id):
        serializer = GradeCategorySerializer(data=request.data)
        parent = GradeCategory.objects.filter(pk=id).first()

        # Validate that user has correct access rights
        root = parent
        while root.parent_category is not None:
            root = root.parent_category
        project_group = root.grade_calculation.project_group
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project_group)
        allowed_rights = ["A", "O"]
        has_rights = user_project_groups.count() > 0 and user_project_groups.first().rights in allowed_rights

        if has_rights and serializer.is_valid():
            grade_category = serializer.save()
            grade_category.parent_category = parent
            grade_category.save()
            for project in project_group.project_set.all():
                for user_project in project.userproject_set.all():
                    add_user_grade_recursive(user_project, grade_category)
            if "start" in request.data.keys() and "end" in request.data.keys() and len(request.data["start"]) > 0 and len(request.data["end"]) > 0:
                grade_milestone = GradeMilestone.objects.create(start=request.data["start"], end=request.data["end"], grade_category=grade_category)
            return JsonResponse(GradeCategorySerializer(grade_category).data)
        return JsonResponse({4: 18})

    def delete(self, request, id):
        grade_category = GradeCategory.objects.filter(pk=id).first()
        root = grade_category
        while root.parent_category is not None:
            root = root.parent_category
        project_group = root.grade_calculation.project_group
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project_group)
        allowed_rights = ["A", "O"]
        has_rights = user_project_groups.count() > 0 and user_project_groups.first().rights in allowed_rights
        if has_rights:
            grade_category.delete()
            return JsonResponse({200: "OK"})
        return JsonResponse({4: 18})


class ProjectGroupGradingView(views.APIView):
    def get(self, request, id):
        project_group = ProjectGroup.objects.filter(pk=id).first()
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project_group)
        if user_project_groups.count() == 0:
            return JsonResponse({4: 18})
        root_category = project_group.grade_calculation.grade_category
        print(root_category)
        return JsonResponse(GradeCategorySerializer(root_category).data)


class ProjectGradesView(views.APIView):
    def get(self, request, id):
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
        if not request.user.is_superuser:
            return JsonResponse({4: 18})

        users = request.data["data"]
        user_objects = []
        for user in users:
            email = user + "@ttu.ee"
            sub_data = {}
            sub_data["username"] = user
            sub_data["email"] = email
            sub_data["password"] = "".join([random.choice(string.ascii_lowercase) for _ in range(20)])
            sub_data["password_confirm"] = sub_data["password"]
            if "." in user:
                sub_data["first_name"] = user.split(".")[0]
                sub_data["last_name"] = ".".join(user.split(".")[1:])
            else:
                sub_data["first_name"] = user[:len(user) // 2]
                sub_data["last_name"] = user[len(user) // 2:]
            serializer = RegisterSerializer(data=sub_data)
            serializer.is_valid()
            user_object = serializer.save()
            Profile.objects.create(user=user_object, actual_account=False)
            user_objects.append(user_object)

        project_group = ProjectGroup.objects.filter(pk=id).first()
        projects = Project.objects.filter(project_group=project_group)
        grade_category_root = project_group.grade_calculation.grade_category
        for project in projects:
            users_found = []
            for repo in project.repository_set.all():
                answer_json = get_members_from_repo(repo, request.user)
                for member in answer_json:
                    for user in user_objects:
                        if user.username in users_found:
                            continue
                        if member["username"] == user.username:
                            user_project = UserProject.objects.create(rights="M", account=user, project=project)
                            add_user_grade_recursive(user_project, grade_category_root)
                            users_found.append(user.username)
                            print(f"{member['username']} found in project {project.name}")
        return JsonResponse({200: "OK"})


class MockAccounts(views.APIView):
    def get(self, request):
        accounts = User.objects.filter(profile__actual_account=False)
        return JsonResponse([x.id for x in accounts], safe=False)


def pick_user_grade(query):
    options = query.all()
    order = ["M", "A", "P"]
    for target_type in order:
        for option in options:
            if option.grade_type == target_type:
                return option


class GradeUserView(views.APIView):
    def post(self, request, user_id, grade_id):
        print(f"Grading user {user_id} and grade {grade_id} with data {request.data}")
        user_project = UserProject.objects.filter(pk=user_id).first()
        grade = GradeCategory.objects.filter(pk=grade_id).first()
        search = UserGrade.objects.filter(user_project=user_project).filter(grade_component=grade)

        added_data = False
        for old_grade in search.all():
            if old_grade.grade_type == "P":
                old_grade.delete()
            elif old_grade.grade_type == "M":
                old_grade.amount = request.data["amount"]
                old_grade.save()
                added_data = True
            elif old_grade.grade_type == "A":
                pass
        if not added_data:
            new_grade = UserGrade.objects.create(amount=request.data["amount"], user_project=user_project, grade_component=grade, grade_type="M")

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
                children_total_potential = func([c.total for c in children])
                children_total_value = func([pick_user_grade(UserGrade.objects.filter(user_project=user_project).filter(grade_component=c)).amount for c in children])

                # TODO: Refactor updating parent as well. For now lets agree to not manually overwrite sum, max or min type grades
                parent_grade = UserGrade.objects.filter(user_project=user_project).filter(grade_component=parent).first()
                parent_grade.amount = parent.total * children_total_value / children_total_potential
                parent_grade.save()
            else:
                break

            grade = parent
            parent = grade.parent_category
        return JsonResponse({200: "OK"})


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
    base_url = "https://gitlab.cs.ttu.ee"
    api_part = "/api/v4"
    token_part = f"?private_token={user.profile.gitlab_token}&per_page=100"

    # Load all milestones
    endpoint_part = f"/projects/{repo.gitlab_id}/milestones"
    answer = requests.get(base_url + api_part + endpoint_part + token_part).json()
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
        if Issue.objects.filter(gitlab_id=gitlab_id).count() == 0:
            issue_object = Issue.objects.create(gitlab_id=gitlab_id, title=title, gitlab_iid=gitlab_iid)
            if milestone is not None:
                IssueMilestone.objects.create(issue=issue_object, milestone=Milestone.objects.filter(gitlab_id=milestone['id']).first())
                pass

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
    return repo


class RepositoryUpdateView(views.APIView):
    def get(self, request, id):
        # TODO: add validation
        repo = update_repository(id, request.user, [])
        return JsonResponse({200: "OK", "data": RepositorySerializer(repo).data})


class ProjectGroupUpdateView(views.APIView):
    def get(self, request, id):
        project_group = ProjectGroup.objects.filter(pk=id).first()
        repos = []
        new_users = []
        for project in project_group.project_set.all():
            for repository in project.repository_set.all():
                repos.append(repository.pk)
        for i, repo in enumerate(repos):
            update_repository(repo, request.user, new_users)
            print(f"{100 * i / len(repos)}% done refreshing repos")
        print(new_users)
        return JsonResponse({200: "OK", "data": ProjectGroupSerializer(project_group).data})
