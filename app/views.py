import string

import requests
import random
import hashlib
import time
import threading
import datetime
import colorsys

from rest_framework import views
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from .models import ProjectGroup, UserProjectGroup, Profile, Project, Repository, GradeCategory, GradeCalculation, \
    GradeMilestone, UserProject, UserGrade, Milestone, TimeSpent, Feedback, Process, ProjectGrade

from .serializers import ProjectGroupSerializer, ProjectSerializer, RepositorySerializer, GradeCategorySerializer, \
    GradeCategorySerializerWithGrades, MilestoneSerializer, GradeMilestoneSerializer, ProcessSerializer, \
    FeedbackSerializer

from . import grading_tree
from . import model_traversal
from . import gitlab_helper
from . import helpers
from . import milestone_logic
from . import constants
from . import custom_serializers
from . import security


class ProjectGroupView(views.APIView):
    def get(self, request):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        queryset = ProjectGroup.objects.filter(user_project_groups__account=request.user)
        serializer = ProjectGroupSerializer(queryset, many=True)
        data = serializer.data
        for point in data:
            point["rights"] = [conn.rights for conn in UserProjectGroup.objects.filter(account=request.user).filter(project_group=point["id"]).all()]
        return JsonResponse(data, safe=False)

    def post(self, request):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        serializer = ProjectGroupSerializer(data=request.data)
        if serializer.is_valid():
            project_group = serializer.save()
            UserProjectGroup.objects.create(rights="O", account=request.user, project_group=project_group)
            grade_category = GradeCategory.objects.create(name="root", grade_type="S")
            GradeCalculation.objects.create(grade_category=grade_category, project_group=project_group)
        return JsonResponse({})


class ProjectGroupLoadProjectsView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        print(f"Getting projects for project group {id}")
        group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, group, ["A", "O"]):
            return JsonResponse(constants.no_access_json)

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
            members = [member["username"] for member in gitlab_helper.get_members_from_repo(repo, request.user, True)]
            for user in User.objects.filter(username__in=members).all():
                rights_query = UserProjectGroup.objects.filter(account=user).filter(project_group=group)
                if rights_query.count() > 0 and rights_query.first().rights in ["A", "O"]:
                    continue
                user_project = UserProject.objects.create(rights="M", account=user, project=project_object, colour=helpers.random_colour())
                grading_tree.add_user_grade(user_project, group)

        return JsonResponse({"data": data})


class ProjectsView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, group, ["A", "O", "V"]):
            return JsonResponse(constants.no_access_json)
        projects = Project.objects.filter(project_group=group).all()
        root_category = group.grade_calculation.grade_category
        data = []
        base_grade_filter = UserGrade.objects.filter(grade_category=root_category)
        grade_milestones = [x for x in model_traversal.get_grade_milestones_by_projectgroup(group)]
        for project in projects:
            dat = ProjectSerializer(project).data

            dat["teachers"] = [x.account.username for x in project.userproject_set.filter(rights="T").all()]
            dat["mentors"] = [x.account.username for x in project.userproject_set.filter(rights="E").all()]

            devs = []
            for dev in project.userproject_set.filter(disabled=False).all():
                dev_data = {}
                grade_object = base_grade_filter.filter(user_project=dev).first()
                dev_data["points"] = grade_object.amount
                dev_data["name"] = dev.account.username
                dev_data["colour"] = dev.colour
                devs.append(dev_data)

            milestones = milestone_logic.get_grademilestone_data_for_project(project, grade_milestones)

            dat["users"] = devs
            dat["milestones"] = milestones
            data.append(dat)
        return JsonResponse(data, safe=False)


class RepositoryView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project = Project.objects.filter(pk=id).first()
        if not security.user_has_access_to_project(request.user, project):
            return JsonResponse(constants.no_access_json)
        grade_milestones = [x for x in model_traversal.get_grade_milestones_by_projectgroup(project.project_group)]
        repos = Repository.objects.filter(project=project)
        data = {}
        data["repositories"] = RepositorySerializer(repos, many=True).data
        devs = {x.account.username: {
            "time_spent": 0,
            "lines_added": 0,
            "lines_removed": 0,
            "colour": x.colour
        } for x in UserProject.objects.filter(project=project).filter(disabled=False).all()}
        for repo in repos.all():
            for commit in repo.commit_set.all():
                user = commit.author.account
                if user is not None and user.username in devs.keys():
                    # TODO: think of a better way to differentiate between "actual" lines and just pushing large files
                    if commit.lines_added < 2500:
                        devs[user.username]["lines_added"] += commit.lines_added
                    if commit.lines_removed < 2500:
                        devs[user.username]["lines_removed"] += commit.lines_removed
        for dev in UserProject.objects.filter(project=project).filter(disabled=False).all():
            times_spent = TimeSpent.objects.filter(user=dev.account).filter(issue__milestone__repository__project=project).all()
            devs[dev.account.username]["time_spent"] = sum([time_spend.amount for time_spend in times_spent]) / 60
        dev_list = []
        for key, val in devs.items():
            val["username"] = key
            dev_list.append(val)
        data["developers"] = dev_list
        data["project"] = {}
        for key in ["time_spent", "lines_added", "lines_removed"]:
            data["project"][key] = sum([x[key] for x in dev_list])
        data["milestones"] = milestone_logic.get_grademilestone_data_for_project(project, grade_milestones, True)
        return JsonResponse(data, safe=False)


class ProfileView(views.APIView):
    def put(self, request):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        profile = Profile.objects.filter(user=request.user).first()
        profile.gitlab_token = request.data["gitlab_token"]
        profile.save()
        return JsonResponse({})


class GradeCategoryView(views.APIView):
    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
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
                    grading_tree.add_user_grade_recursive(user_project, grade_category)
            if "start" in request.data.keys() and "end" in request.data.keys() and len(request.data["start"]) > 0 and len(request.data["end"]) > 0:
                amount = model_traversal.get_amount_of_grademilestone_by_projectgroup(project_group)
                GradeMilestone.objects.create(
                    start=request.data["start"],
                    end=request.data["end"],
                    grade_category=grade_category,
                    milestone_order_id=amount + 1
                )
            return JsonResponse(GradeCategorySerializer(grade_category).data)
        return JsonResponse({4: 18})

    def delete(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
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
                all_milestones = model_traversal.get_grade_milestones_by_projectgroup(project_group)
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
            return JsonResponse(constants.anonymous_json)
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O", "V"]):
            return JsonResponse(constants.no_access_json)
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project_group)
        if user_project_groups.count() == 0:
            return JsonResponse({4: 18})
        root_category = project_group.grade_calculation.grade_category
        print(root_category)
        return JsonResponse(GradeCategorySerializer(root_category).data)


class ProjectGradesView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project = Project.objects.filter(pk=id).first()
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project.project_group)
        if user_project_groups.count() == 0:
            # TODO: If user_projects has users, then the request came from student, he should see his own grades.
            return JsonResponse({4: 18})

        project_group = project.project_group
        root_category = project_group.grade_calculation.grade_category

        users = [user_project.id for user_project in UserProject.objects.filter(project=project).all()]
        return JsonResponse(GradeCategorySerializerWithGrades(root_category, context={"user_projects": users}).data)


class RootAddUsers(views.APIView):
    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        if not request.user.is_superuser:
            return JsonResponse(constants.no_access_json)

        users = request.data["data"]
        user_objects = []
        for user in users:
            gitlab_helper.create_user(user, user_objects)

        project_group = ProjectGroup.objects.filter(pk=id).first()
        projects = Project.objects.filter(project_group=project_group)
        grade_category_root = project_group.grade_calculation.grade_category
        for project in projects:
            users_found = []
            for repo in project.repository_set.all():
                answer_json = gitlab_helper.get_members_from_repo(repo, request.user, False)
                for member in answer_json:
                    for user in user_objects:
                        if user.username in users_found:
                            continue
                        if member["username"] == user.username:
                            if UserProject.objects.filter(account=user).filter(project=project).count() == 0:
                                user_project = UserProject.objects.create(rights="M", account=user, project=project, colour=helpers.random_colour())
                                grading_tree.add_user_grade_recursive(user_project, grade_category_root)
                                users_found.append(user.username)
                                print(f"{member['username']} found in project {project.name}")
        return JsonResponse({200: "OK"})


class MockAccounts(views.APIView):
    def get(self, request):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        if not request.user.is_superuser:
            return JsonResponse(constants.no_access_json)
        accounts = User.objects.filter(profile__actual_account=False)
        return JsonResponse([x.id for x in accounts], safe=False)


class GradeUserView(views.APIView):
    def post(self, request, user_id, grade_id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = model_traversal.project_group_of_grade_category_id(grade_id)
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
            return JsonResponse(constants.no_access_json)
        print(f"Grading user {user_id} and grade {grade_id} with data {request.data}")
        grading_tree.grade(user_id, grade_id, request.data["amount"])
        return JsonResponse({200: "OK"})


class RepositoryUpdateView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        if not security.user_has_access_to_project(request.user, Repository.objects.filter(pk=id).first().project):
            return JsonResponse(constants.no_access_json)
        repo = gitlab_helper.update_repository(id, request.user, [])
        return JsonResponse({200: "OK", "data": RepositorySerializer(repo).data})


class ProjectGroupUpdateView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
            return JsonResponse(constants.no_access_json)
        name = "project group update"
        hid = hashlib.sha256()
        [hid.update(str(x).encode()) for x in [name, id]]
        old = Process.objects.filter(id_hash=hid.hexdigest()).filter(status="O")
        if old.count() > 0:
            old_p = old.first()
            return JsonResponse({
                "id": old_p.pk,
                "hash": old_p.hash
            })

        h = hashlib.sha256()
        [h.update(str(x).encode()) for x in [time.time(), name, id, request.user.pk]]
        process = Process.objects.create(hash=h.hexdigest(), id_hash=hid.hexdigest(), type="SG", status="O", completion_percentage=0)
        process.save()
        t = threading.Thread(target=gitlab_helper.update_all_repos_in_group, args=[project_group, request.user, process], daemon=True)
        t.start()
        return JsonResponse({
            "id": process.pk,
            "hash": process.hash
        })


class ProjectMilestonesView(views.APIView):
    def get(self, request, id):
        # TODO: repurpose this endpoint
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        if not security.user_has_access_to_project(request.user, Project.objects.filter(id=id).first()):
            return JsonResponse(constants.no_access_json)
        data = []
        i = 1
        name = ""
        while True:
            res = milestone_logic.get_milestone_data_for_project(request, id, i)
            if res["status"] == 418:
                break
            name = res["project_name"]
            data.append({"milestone_number": i, "milestone_data": res["project_data"]})
            i += 1
        return JsonResponse({"status": 200, "project_name": name, "project_data": data})


class GroupSummaryMilestoneDataView(views.APIView):
    def get(self, request, id, milestone_id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        data = []
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
            return JsonResponse(constants.no_access_json)
        for project in project_group.project_set.all():
            project_res = milestone_logic.get_milestone_data_for_project(request, project.pk, milestone_id)
            if project_res["status"] == 418:
                return JsonResponse(project_res)
            del project_res["status"]
            data.append(project_res)
        return JsonResponse({200: "OK", "data": data})


class ProjectMilestoneDataView(views.APIView):
    def get(self, request, id, milestone_id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        if not security.user_has_access_to_project(request.user, Project.objects.filter(pk=id).first()):
            return JsonResponse(constants.no_access_json)
        res = milestone_logic.get_milestone_data_for_project(request, id, milestone_id)
        if res["status"] == 418:
            return JsonResponse(res)
        del res["status"]
        return JsonResponse({200: "OK", "data": res})


class ProjectMilestoneTimeSpentView(views.APIView):
    def get(self, request, id, milestone_id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project = Project.objects.filter(pk=id).first()
        if not security.user_has_access_to_project(request.user, project):
            return JsonResponse(constants.no_access_json)
        milestone = model_traversal.get_grademilestone_by_projectgroup_and_milestone_order_number(project.project_group, milestone_id)
        if milestone is None:
            return JsonResponse({"status": 418, "error": f"Milestone {milestone_id} not found for project {id}."})

        promised_json = []

        user_projects = UserProject.objects.filter(project=project).all()
        for user_project in user_projects:
            promised_json += TimeSpent.objects.filter(user=user_project.account).filter(issue__milestone__grade_milestone=milestone).all()
        return JsonResponse(custom_serializers.serialize_time_spent(promised_json), safe=False)


class ParametricTimeSpentView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project = Project.objects.filter(pk=id).first()
        if not security.user_has_access_to_project(request.user, project):
            return JsonResponse(constants.no_access_json)
        user_projects = UserProject.objects.filter(project=project).all()
        dat = request.GET
        promised_json = []
        for user_project in user_projects:
            base_filter = TimeSpent.objects.filter(user=user_project.account)
            if "start" in dat.keys() and "end" in dat.keys():
                base_filter = base_filter.filter(time__range=[dat["start"], dat["end"]])
            elif "start" in dat.keys():
                base_filter = base_filter.filter(time__gte=dat["start"])
            elif "end" in dat.keys():
                base_filter = base_filter.filter(time__lte=dat["end"])
            promised_json += base_filter.all()
        return JsonResponse(custom_serializers.serialize_time_spent(promised_json), safe=False)


class BulkGradeView(views.APIView):
    def post(self, request):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        checked = False

        for sub_grade in request.data:
            if not checked:
                project_group = model_traversal.project_group_of_grade_category_id(sub_grade["grade_id"])
                if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
                    return JsonResponse(constants.no_access_json)
                checked = True
            grading_tree.grade(sub_grade["user_group_id"], sub_grade["grade_id"], sub_grade["points"])
        return JsonResponse({200: "OK"})


class FeedbackView(views.APIView):

    field_requirements = {
        "AP": [],
        "PA": ["project"],
        "PM": ["project", "gradeMilestone"],
        "UA": ["userProject"],
        "UM": ["userProject", "gradeMilestone"]
    }

    objects = {
        "project": Project.objects,
        "gradeMilestone": GradeMilestone.objects,
        "userProject": UserProject.objects
    }

    def get(self, request):
        # TODO: Add authentication, but this is tricky and not very critical.
        dat = request.GET
        if "type" not in dat.keys():
            return JsonResponse({"Error": "Incorrect fields"}, status=400)
        feedbacks = Feedback.objects.filter(type=dat["type"])
        for req in self.field_requirements[dat["type"]]:
            if req not in dat.keys():
                return JsonResponse({"Error": "Incorrect fields"}, status=400)
            if req == "project":
                feedbacks = feedbacks.filter(project=dat[req])
            elif req == "gradeMilestone":
                feedbacks = feedbacks.filter(grade_milestone=dat[req])
            elif req == "userProject":
                feedbacks = feedbacks.filter(user=dat[req])
        return JsonResponse(FeedbackSerializer(feedbacks, many=True).data, safe=False)

    def post(self, request):
        # TODO: Add authentication, but is okay for now, because isn't critical functionality.
        dat = request.data
        if "feedback" not in dat.keys() or "type" not in dat.keys():
            return JsonResponse({"Error": "Incorrect fields"}, status=400)
        feedback = Feedback.objects.create(text=dat["feedback"], type=dat["type"], time=datetime.datetime.now())
        if not request.user.is_anonymous:
            feedback.commenter = request.user
        for req in self.field_requirements[dat["type"]]:
            if req not in dat.keys():
                return JsonResponse({"Error": "Incorrect fields"}, status=400)
        for req in self.field_requirements[dat["type"]]:
            if req == "project":
                feedback.project = Project.objects.filter(pk=dat[req]).first()
            elif req == "gradeMilestone":
                project = Project.objects.filter(pk=dat["project"]).first() if "project" in dat.keys() else UserProject.objects.filter(pk=dat["userProject"]).first().project
                feedback.grade_milestone = model_traversal.get_grademilestone_by_projectgroup_and_milestone_order_number(project.project_group, dat[req])
            elif req == "userProject":
                feedback.user = GradeMilestone.objects.filter(pk=dat[req]).first()
        feedback.save()
        return JsonResponse({})


class ProjectMilestoneConnectionsView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project = Project.objects.filter(pk=id).first()
        if not security.user_has_access_to_project(request.user, project):
            return JsonResponse(constants.no_access_json)

        # Grade milestones
        grade_milestones = model_traversal.get_grade_milestones_by_projectgroup(project.project_group)
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
            return JsonResponse(constants.anonymous_json)
        repo_milestone = Milestone.objects.filter(pk=id).first()
        if not security.user_has_access_to_project(request.user, repo_milestone.repository.project):
            return JsonResponse(constants.no_access_json)
        if request.data["id"] != -1:
            grade_milestone = GradeMilestone.objects.filter(pk=request.data["id"]).first()
        else:
            grade_milestone = None
        # TODO: Check that connection is allowed
        if grade_milestone is not None:
            repo_milestone_project_group = repo_milestone.repository.project.project_group
            root_category = model_traversal.get_root_category(grade_milestone.grade_category)
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


class ProjectAddUserView(views.APIView):
    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse({}, status=401)
        project = Project.objects.filter(pk=id).first()
        project_group = project.project_group
        user_roles_project = UserProject.objects.filter(project=project).filter(account=request.user).all()
        user_roles_project_group = UserProjectGroup.objects.filter(project_group=project_group).filter(account=request.user).all()
        all_rights = list(user_roles_project) + list(user_roles_project_group)
        max_rights = max([UserProject.rights_hierarchy.index(x.rights) for x in all_rights]) if len(all_rights) > 0 else -1
        target_rights = UserProject.rights_hierarchy.index(request.data["rights"])
        if target_rights >= max_rights:
            return JsonResponse({}, status=401)
        user = User.objects.filter(pk=request.data["user"]).first()
        disabled = request.data["rights"] != "M"
        UserProject.objects.create(rights=request.data["rights"], account=user, project=project, disabled=disabled, colour=helpers.random_colour())
        return JsonResponse({})


class GradeCategoryRecalculateView(views.APIView):
    def get(self, request, id):
        grade_category = GradeCategory.objects.filter(pk=id).first()
        project_group = model_traversal.get_root_category(grade_category).grade_calculation.project_group
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
            return JsonResponse({}, status=401)
        grading_tree.recalculate_grade_category(grade_category)
        return JsonResponse({})


class ChangeDevColourView(views.APIView):
    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        user_project = UserProject.objects.filter(project=id).filter(account__username=request.data["username"])
        if user_project.count() == 0:
            return JsonResponse({}, 404)
        user_project = user_project.first()
        if not (security.user_has_access_to_project_with_security_level(request.user, user_project.project, ["O", "A", "T", "E"]) or user_project.account == request.user):
            return JsonResponse({}, 404)
        user_project.colour = request.data["colour"]
        user_project.save()
        return JsonResponse({})


class ProjectRepoConnectionView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, group, ["A", "O"]):
            return JsonResponse(constants.no_access_json)
        projects = Project.objects.filter(project_group=group).all()
        repos = []
        for project in projects:
            repos += Repository.objects.filter(project=project).all()
        return JsonResponse({"projects": ProjectSerializer(projects, many=True).data, "repos": RepositorySerializer(repos, many=True).data})


class RepoSetProjectView(views.APIView):
    def put(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        repo = Repository.objects.filter(pk=id).first()
        old_project = repo.project
        old_group = old_project.project_group
        if not security.user_has_access_to_project_group_with_security_level(request.user, old_group, ["A", "O"]):
            return JsonResponse(constants.no_access_json)
        new_project = Project.objects.filter(pk=request.data["id"]).first()
        new_group = new_project.project_group
        if old_group != new_group:
            return JsonResponse({"Error": "Old project group does not match new project group"}, status=409)
        repo.project = new_project
        repo.save()
        return JsonResponse({})


class AddNewProject(views.APIView):
    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, group, ["A", "O"]):
            return JsonResponse(constants.no_access_json)
        project = Project.objects.create(name=request.data["name"], project_group=group)
        return JsonResponse(ProjectSerializer(project).data)


class AddNewRepo(views.APIView):
    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project = Project.objects.filter(pk=id).first()
        if not security.user_has_access_to_project(request.user, project):
            return JsonResponse(constants.no_access_json)
        repo = Repository.objects.create(url=request.data["url"], gitlab_id=request.data["gitlab_id"], name=request.data["name"], project=project)
        gitlab_helper.update_repository(repo.pk, request.user, [])
        return JsonResponse(RepositorySerializer(repo).data)
