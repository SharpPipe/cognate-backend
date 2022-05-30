import csv

import requests
import hashlib
import time
import threading
import datetime

from rest_framework import views
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from .models import ProjectGroup, UserProjectGroup, Profile, Project, Repository, AssessmentCategory, \
    AssessmentCalculation, AssessmentMilestone, UserProject, UserAssessment, Milestone, TimeSpent, Feedback, Process, \
    AutomateAssessment, ProjectGroupInvitation, ProjectAssessment

from .serializers import ProjectGroupSerializer, ProjectSerializer, RepositorySerializer, \
    AssessmentCategorySerializer, AssessmentCategorySerializerWithAssessments, MilestoneSerializer, \
    AssessmentMilestoneSerializer, ProcessSerializer, FeedbackSerializer

from . import assessment_tree
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
            assessment_category = AssessmentCategory.objects.create(name="root", assessment_type="S")
            AssessmentCalculation.objects.create(assessment_category=assessment_category, project_group=project_group)
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
                assessment_tree.add_user_assessment(user_project, group)

        return JsonResponse({"data": data})


class ProjectsView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, group, ["A", "O", "V"]):
            return JsonResponse(constants.no_access_json)
        projects = Project.objects.filter(project_group=group).all()
        root_category = group.assessment_calculation.assessment_category
        data = []
        rights = [conn.rights for conn in UserProjectGroup.objects.filter(account=request.user).filter(project_group=group).all()]
        base_assessment_filter = UserAssessment.objects.filter(assessment_category=root_category)
        assessment_milestones = [x for x in model_traversal.get_assessment_milestones_by_projectgroup(group)]
        json_warnings = []
        for project in projects:
            dat = ProjectSerializer(project).data

            dat["teachers"] = [x.account.username for x in project.userproject_set.filter(rights="T").all()]
            dat["mentors"] = [x.account.username for x in project.userproject_set.filter(rights="E").all()]

            devs = []
            for dev in project.userproject_set.filter(disabled=False).filter(rights="M").all():
                dev_data = {}
                assessment_object = base_assessment_filter.filter(user_project=dev).first()
                if assessment_object is None:
                    json_warnings.append(f"Developer {dev} does not seem to have an assessment object.")
                dev_data["points"] = assessment_object.amount if assessment_object is not None else -1
                dev_data["name"] = dev.account.username
                dev_data["colour"] = dev.colour
                devs.append(dev_data)

            milestones = milestone_logic.get_assessmentmilestone_data_for_project(project, assessment_milestones)

            dat["users"] = devs
            dat["milestones"] = milestones
            data.append(dat)
        return JsonResponse({"data": data, "rights": rights, "active_milestones": len(assessment_milestones), "total_milestones": 7, "warnings": json_warnings}, safe=False)

    def put(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, group, ["A", "O"]):
            return JsonResponse(constants.no_access_json)
        if "name" in request.data.keys():
            group.name = request.data["name"]
        if "description" in request.data.keys():
            group.description = request.data["description"]
        if "gitlab_token" in request.data.keys():
            group.gitlab_token = request.data["gitlab_token"]
        group.save()
        return JsonResponse({})


class RepositoryView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project = Project.objects.filter(pk=id).first()
        if not security.user_has_access_to_project(request.user, project):
            return JsonResponse(constants.no_access_json)
        assessment_milestones = [x for x in model_traversal.get_assessment_milestones_by_projectgroup(project.project_group)]
        repos = Repository.objects.filter(project=project)
        data = {}
        data["repositories"] = RepositorySerializer(repos, many=True).data
        user_projects = [x for x in UserProject.objects.filter(project=project).filter(disabled=False).all()]
        devs = {x.account.username: {
            "time_spent": 0,
            "lines_added": x.total_lines_added,
            "lines_removed": x.total_lines_removed,
            "colour": x.colour
        } for x in user_projects}
        for repo in repos.all():
            for commit in repo.commit_set.filter(counted_in_user_project_total=False).all():
                user = commit.author.account
                if user is not None and user.username in devs.keys():
                    # TODO: think of a better way to differentiate between "actual" lines and just pushing large files
                    if commit.lines_added < 2500:
                        devs[user.username]["lines_added"] += commit.lines_added
                    if commit.lines_removed < 2500:
                        devs[user.username]["lines_removed"] += commit.lines_removed
                    commit.counted_in_user_project_total = True
                    commit.save()
        for user_project in user_projects:
            user_project.total_lines_added = devs[user_project.account.username]["lines_added"]
            user_project.total_lines_removed = devs[user_project.account.username]["lines_removed"]
            user_project.save()

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
        data["milestones"] = milestone_logic.get_assessmentmilestone_data_for_project(project, assessment_milestones, True)
        data["active_milestones"] = len(data["milestones"])
        data["total_milestones"] = 7
        return JsonResponse(data, safe=False)


class ProfileView(views.APIView):
    def get(self, request):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        profile = Profile.objects.filter(user=request.user).first()
        return JsonResponse(constants.successful_data_json("Successfully got profile.", {"identifier": profile.identifier, "id": profile.pk, "store_password": profile.store_passwords_in_local_storage}))

    def put(self, request):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        profile = Profile.objects.filter(user=request.user).first()
        if "gitlab_token" in request.data.keys():
            profile.gitlab_token = request.data["gitlab_token"]
        if "store_password" in request.data.keys():
            profile.store_passwords_in_local_storage = request.data["store_password"]
        profile.save()
        if "password" in request.data.keys():
            security.encrypt_token(request.user, request.data["password"])
        return JsonResponse({})


class AssessmentCategoryView(views.APIView):
    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = model_traversal.get_project_group_of_assessment_category_id(id)
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
            return JsonResponse(constants.no_access_json)
        serializer = AssessmentCategorySerializer(data=request.data)
        parent = AssessmentCategory.objects.filter(pk=id).first()
        if request.data["project_assessment"] is False and parent.project_assessment is True:
            return JsonResponse({"Error": "Project assessment can't have non project assessment children."}, status=400)
        if not serializer.is_valid():
            return JsonResponse({"Error": "Invalid data in serializer."}, status=400)
        if request.data["assessment_type"] == "A":
            if "automation_type" not in request.data.keys():
                return JsonResponse({"Error": "Assessment type is automatic, but missing automation_type field."}, status=400)
            if request.data["automation_type"] in "LT":
                if "amount_needed" not in request.data.keys():
                    return JsonResponse({"Error": "Automation type needs amount, but no amount field given."}, status=400)
        assessment_category = serializer.save()
        assessment_category.parent_category = parent
        assessment_category.save()
        assessment_tree.add_assessments_to_category(assessment_category, project_group)
        if "start" in request.data.keys() and "end" in request.data.keys() and len(request.data["start"]) > 0 and len(request.data["end"]) > 0 and not assessment_tree.assessment_category_has_milestone_parent(assessment_category):
            amount = model_traversal.get_amount_of_assessmentmilestone_by_projectgroup(project_group)
            AssessmentMilestone.objects.create(
                start=request.data["start"],
                end=request.data["end"],
                assessment_category=assessment_category,
                milestone_order_id=amount + 1
            )
        if assessment_category.assessment_type == "A":
            if request.data["automation_type"] in "LT":
                AutomateAssessment.objects.create(automation_type=request.data["automation_type"], amount_needed=request.data["amount_needed"], assessment_category=assessment_category)
            elif request.data["automation_type"] == "R":
                AutomateAssessment.objects.create(automation_type=request.data["automation_type"], amount_needed=0, assessment_category=assessment_category)
        assessment_tree.recalculate_assessment_category(assessment_category)
        return JsonResponse(AssessmentCategorySerializer(assessment_category).data)

    def delete(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        assessment_category = AssessmentCategory.objects.filter(pk=id).first()
        root = assessment_category
        while root.parent_category is not None:
            root = root.parent_category
        project_group = root.assessment_calculation.project_group
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project_group)
        allowed_rights = ["O"]
        has_rights = user_project_groups.count() > 0 and user_project_groups.first().rights in allowed_rights
        parent = assessment_category.parent_category
        if has_rights:
            try:
                target_milestone = assessment_category.assessmentmilestone
            except ObjectDoesNotExist:
                # Is not a milestone
                assessment_category.delete()
                assessment_tree.recalculate_assessment_category(parent)
                return JsonResponse({200: "OK"})
            else:
                all_milestones = model_traversal.get_assessment_milestones_by_projectgroup(project_group)
                for milestone in all_milestones:
                    if milestone.milestone_order_id > target_milestone.milestone_order_id:
                        milestone.milestone_order_id = milestone.milestone_order_id - 1
                        milestone.save()
                target_milestone.delete()
                assessment_category.delete()
                assessment_tree.recalculate_assessment_category(parent)
                return JsonResponse({200: "OK"})
        return JsonResponse({4: 18})

    def put(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = model_traversal.get_project_group_of_assessment_category_id(id)
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
            return JsonResponse(constants.no_access_json)
        assessment_category = AssessmentCategory.objects.filter(pk=id).first()
        if "total" in request.data.keys():
            assessment_category.total = request.data["total"]
        if "description" in request.data.keys():
            assessment_category.description = request.data["description"]
        if "name" in request.data.keys():
            assessment_category.name = request.data["name"]
        gm_query = AssessmentMilestone.objects.filter(assessment_category=assessment_category)
        if gm_query.count() > 0:
            gm = gm_query.first()
            if "start" in request.data.keys():
                gm.start = request.data["start"]
            if "end" in request.data.keys():
                gm.end = request.data["end"]
            gm.save()
        assessment_category.save()
        return JsonResponse(AssessmentCategorySerializer(assessment_category).data)


class AssessmentCategoryCopyView(views.APIView):
    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = model_traversal.get_project_group_of_assessment_category_id(id)
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
            return JsonResponse(constants.no_access_json)
        assessment_category = AssessmentCategory.objects.filter(pk=id).first()
        assessment_tree.generate_assessment_category_copy(assessment_category, assessment_category.parent_category)
        return JsonResponse({})


class ProjectGroupAssessmentView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O", "V"]):
            return JsonResponse(constants.no_access_json)
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project_group)
        if user_project_groups.count() == 0:
            return JsonResponse({4: 18})
        root_category = project_group.assessment_calculation.assessment_category
        print(root_category)
        return JsonResponse(AssessmentCategorySerializer(root_category).data)


class ProjectAssessmentsView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project = Project.objects.filter(pk=id).first()
        user_project_groups = UserProjectGroup.objects.filter(account=request.user).filter(project_group=project.project_group)
        if user_project_groups.count() == 0:
            # TODO: If user_projects has users, then the request came from student, he should see his own assessments.
            return JsonResponse({4: 18})

        project_group = project.project_group
        root_category = project_group.assessment_calculation.assessment_category

        users = [user_project.id for user_project in UserProject.objects.filter(project=project).all()]
        return JsonResponse(AssessmentCategorySerializerWithAssessments(root_category, context={"user_projects": users}).data)


class AssessUserView(views.APIView):
    def post(self, request, user_id, assessment_id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = model_traversal.get_project_group_of_assessment_category_id(assessment_id)
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
            return JsonResponse(constants.no_access_json)
        print(f"Assessing user {user_id} and assessment {assessment_id} with data {request.data}")
        assessment_tree.assessment(user_id, assessment_id, request.data["amount"])
        return JsonResponse({200: "OK"})


class RepositoryUpdateView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        if not security.user_has_access_to_project(request.user, Repository.objects.filter(pk=id).first().project):
            return JsonResponse(constants.no_access_json)
        user_token = security.get_user_token(request.user, request.data["password"])
        repo = gitlab_helper.update_repository(id, request.user, [], user_token)
        return JsonResponse({200: "OK", "data": RepositorySerializer(repo).data})


class ProjectGroupUpdateView(views.APIView):
    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
            return JsonResponse(constants.no_access_json)
        user_token = None
        if "password" in request.data:
            security.encrypt_token(request.user, request.data["password"])
            user_token = security.get_user_token(request.user, request.data["password"])
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
        t = threading.Thread(target=gitlab_helper.update_all_repos_in_group, args=[project_group, request.user, process, user_token], daemon=True)
        t.start()
        return JsonResponse({
            "id": process.pk,
            "hash": process.hash
        })


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
        milestone = model_traversal.get_assessmentmilestone_by_projectgroup_and_milestone_order_number(project.project_group, milestone_id)
        if milestone is None:
            return JsonResponse({"status": 418, "error": f"Milestone {milestone_id} not found for project {id}."})

        promised_json = []

        user_projects = UserProject.objects.filter(project=project).filter(disabled=False).all()
        for user_project in user_projects:
            promised_json += TimeSpent.objects.filter(user=user_project.account).filter(issue__milestone__assessment_milestone=milestone).all()
        return JsonResponse(custom_serializers.serialize_time_spent(promised_json), safe=False)


class ParametricTimeSpentView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project = Project.objects.filter(pk=id).first()
        if not security.user_has_access_to_project(request.user, project):
            return JsonResponse(constants.no_access_json)
        user_projects = UserProject.objects.filter(project=project).filter(disabled=False).all()
        dat = request.GET
        promised_json = []
        for user_project in user_projects:
            base_filter = TimeSpent.objects.filter(user=user_project.account).filter(issue__repository__project=project)
            if "start" in dat.keys() and "end" in dat.keys():
                base_filter = base_filter.filter(time__range=[dat["start"], dat["end"]])
            elif "start" in dat.keys():
                base_filter = base_filter.filter(time__gte=dat["start"])
            elif "end" in dat.keys():
                base_filter = base_filter.filter(time__lte=dat["end"])
            promised_json += base_filter.all()
        return JsonResponse(custom_serializers.serialize_time_spent(promised_json), safe=False)


class BulkAssessView(views.APIView):
    def post(self, request):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        checked = False

        for sub_assessment in request.data:
            if not checked:
                project_group = model_traversal.get_project_group_of_assessment_category_id(sub_assessment["assessment_id"])
                if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
                    return JsonResponse(constants.no_access_json)
                checked = True
            assessment_tree.assessment(sub_assessment["user_group_id"], sub_assessment["assessment_id"], sub_assessment["points"])
        return JsonResponse({200: "OK"})


class FeedbackView(views.APIView):

    field_requirements = {
        "AP": [],
        "PA": ["project"],
        "PM": ["project", "assessmentMilestone"],
        "UA": ["userProject"],
        "UM": ["userProject", "assessmentMilestone"]
    }

    objects = {
        "project": Project.objects,
        "assessmentMilestone": AssessmentMilestone.objects,
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
            elif req == "assessmentMilestone":
                feedbacks = feedbacks.filter(assessment_milestone=dat[req])
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
            elif req == "assessmentMilestone":
                project = Project.objects.filter(pk=dat["project"]).first() if "project" in dat.keys() else UserProject.objects.filter(pk=dat["userProject"]).first().project
                feedback.assessment_milestone = model_traversal.get_assessmentmilestone_by_projectgroup_and_milestone_order_number(project.project_group, dat[req])
            elif req == "userProject":
                feedback.user = AssessmentMilestone.objects.filter(pk=dat[req]).first()
        feedback.save()
        return JsonResponse({})


class ProjectMilestoneConnectionsView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project = Project.objects.filter(pk=id).first()
        if not security.user_has_access_to_project(request.user, project):
            return JsonResponse(constants.no_access_json)

        # Assessment milestones
        assessment_milestones = model_traversal.get_assessment_milestones_by_projectgroup(project.project_group)
        gm_serializer = AssessmentMilestoneSerializer(assessment_milestones, many=True)

        # Repository milestones
        milestones = []
        for repository in project.repository_set.all():
            for milestone in repository.milestones.all():
                milestones.append(milestone)
        for milestone in project.milestones.all():
            milestones.append(milestone)
        m_serializer = MilestoneSerializer(milestones, many=True)

        return JsonResponse({
            "assessment_milestones": list(sorted(gm_serializer.data, key=lambda x: x["milestone_order_id"])),
            "milestones": m_serializer.data
        })


class MilestoneSetAssessmentMilestoneView(views.APIView):
    def put(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        repo_milestone = Milestone.objects.filter(pk=id).first()
        if not security.user_has_access_to_project(request.user, model_traversal.get_project_from_milestone(repo_milestone)):
            return JsonResponse(constants.no_access_json)
        if request.data["id"] != -1:
            assessment_milestone = AssessmentMilestone.objects.filter(pk=request.data["id"]).first()
        else:
            assessment_milestone = None
        # TODO: Check that connection is allowed
        if assessment_milestone is not None:
            repo_milestone_project_group = model_traversal.get_project_from_milestone(repo_milestone).project_group
            root_category = model_traversal.get_root_category(assessment_milestone.assessment_category)
            assessment_milestone_project_group = AssessmentCalculation.objects.filter(assessment_category=root_category).first().project_group
            if repo_milestone_project_group != assessment_milestone_project_group:
                print(f"Repository milestone {repo_milestone} and assessment milestone {assessment_milestone} do not have matching project groups.")
                return JsonResponse({418: "ERROR"})

        repo_milestone.assessment_milestone = assessment_milestone
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


class AssessmentCategoryRecalculateView(views.APIView):
    def get(self, request, id):
        assessment_category = AssessmentCategory.objects.filter(pk=id).first()
        project_group = model_traversal.get_root_category(assessment_category).assessment_calculation.project_group
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["A", "O"]):
            return JsonResponse({}, status=401)
        assessment_tree.recalculate_assessment_category(assessment_category)
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
        name = "repo update"
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
        process = Process.objects.create(hash=h.hexdigest(), id_hash=hid.hexdigest(), type="SR", status="O", completion_percentage=0)

        user_token = security.get_user_token(request.user, request.data["password"])

        t = threading.Thread(target=gitlab_helper.update_repository, args=[repo.pk, request.user, [], user_token, process], daemon=True)
        t.start()
        return JsonResponse({
            "id": process.pk,
            "hash": process.hash
        })


class ManageGroupInvitationsView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["O", "A"]):
            return JsonResponse(constants.no_access_json)
        invitations = ProjectGroupInvitation.objects.filter(project_group=project_group).all()
        identifiers = [x.identifier for x in invitations]
        return JsonResponse(constants.successful_data_json("Invitations fetched successfully", {"identifiers": identifiers}))

    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["O", "A"]):
            return JsonResponse(constants.no_access_json)
        identifier = request.data["identifier"]
        if ProjectGroupInvitation.objects.filter(project_group=project_group).filter(identifier=identifier).count() > 0:
            return JsonResponse(constants.successful_empty_json("Invitation for that user already exists. Did not create a new one."))
        ProjectGroupInvitation.objects.create(project_group=project_group, identifier=identifier)
        return JsonResponse(constants.successful_empty_json("Invitation created successfully."))

    def delete(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["O", "A"]):
            return JsonResponse(constants.no_access_json)
        ProjectGroupInvitation.objects.filter(project_group=project_group).filter(identifier=request.data["identifier"]).delete()
        return JsonResponse(constants.successful_empty_json("Invitation successfully deleted"))


class ProfileInvitationView(views.APIView):
    def get(self, request):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        invitations = ProjectGroupInvitation.objects.filter(identifier=request.user.profile.identifier).filter(has_been_declined=False).all()
        groups = [ProjectGroupSerializer(x.project_group).data for x in invitations]
        return JsonResponse(constants.successful_data_json("Successfully got invitations for user.", {"invitations": groups}))


class AcceptGroupInvitationView(views.APIView):
    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = ProjectGroup.objects.filter(pk=id).first()
        invitations = ProjectGroupInvitation.objects.filter(project_group=project_group).filter(identifier=request.user.profile.identifier)
        if invitations.count() == 0:
            return JsonResponse(constants.error_json("This user does not have invitation for that group."), status=403)
        if request.data["accept"]:
            UserProjectGroup.objects.create(rights="B", account=request.user, project_group=project_group)
            invitations.delete()
            return JsonResponse(constants.successful_empty_json("Added user to project group"))
        invitation = invitations.first()
        invitation.has_been_declined = True
        invitation.save()
        return JsonResponse(constants.successful_empty_json("Successfully declined invitation"))


class ProjectGroupUsersView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["O", "A"]):
            return JsonResponse(constants.no_access_json)
        user_project_groups = UserProjectGroup.objects.filter(project_group=project_group).all()
        by_user = {}
        by_role = {role: [] for role in UserProjectGroup.role_hierarchy}
        for user_project_group in user_project_groups:
            account = user_project_group.account
            by_role[user_project_group.rights].append({"username": account.username, "id": account.pk})
            if (account.pk, account.username) not in by_user.keys():
                by_user[(account.pk, account.username)] = []
            by_user[(account.pk, account.username)].append(user_project_group.rights)
        by_role = [{"role": role, "users": users} for role, users in by_role.items()]
        by_user = [{"account": {"id": user[0], "username": user[1]}, "roles": roles} for user, roles in by_user.items()]
        return JsonResponse(constants.successful_data_json("Successfully fetched roles for project group", {"by_user": by_user, "by_role": by_role}))

    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["O", "A"]):
            return JsonResponse(constants.no_access_json)
        if not security.user_has_access_to_project_group_with_security_level_at_least(project_group, request.user, request.data["role"]):
            return JsonResponse(constants.error_json("You are trying to assign a higher level role than you have yourself"))
        target_account = User.objects.filter(pk=request.data["id"]).first()
        current_roles = UserProjectGroup.objects.filter(project_group=project_group).filter(account=target_account)
        if current_roles.count() == 0:
            return JsonResponse(constants.error_json("Tou are trying to give a role to a user who is not in this project group."))
        UserProjectGroup.objects.create(account=target_account, project_group=project_group, rights=request.data["role"])
        return JsonResponse(constants.successful_empty_json("Successfully added user to new role"))

    def delete(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project_group = ProjectGroup.objects.filter(pk=id).first()
        if request.data["id"] == request.user.pk:
            UserProjectGroup.objects.filter(account=request.user).filter(project_group=project_group).filter(rights=request.data["role"]).delete()
            return JsonResponse(constants.successful_empty_json("Successfully removed role"))
        if not security.user_has_access_to_project_group_with_security_level(request.user, project_group, ["O", "A"]):
            return JsonResponse(constants.no_access_json)
        if not security.user_has_access_to_project_group_with_security_level_more_than(project_group, request.user, request.data["role"]):
            return JsonResponse(constants.error_json("You are trying to remove a role equal to or higher than yours"))
        target_user = User.objects.filter(pk=request.data["id"]).first()
        UserProjectGroup.objects.filter(account=target_user).filter(project_group=project_group).filter(rights=request.data["role"]).delete()
        return JsonResponse(constants.successful_empty_json("Successfully removed role from user"))


class ProjectUsersView(views.APIView):
    def get(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project = Project.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_with_security_level(request.user, project, ["A", "O", "M", "T"]):
            return JsonResponse(constants.no_access_json)
        user_projects = UserProject.objects.filter(project=project).all()
        by_user = {}
        by_role = {role: [] for role in UserProject.role_hierarchy}
        for user_project in user_projects:
            account = user_project.account
            by_role[user_project.rights].append({"username": account.username, "id": account.pk})
            if (account.pk, account.username) not in by_user.keys():
                by_user[(account.pk, account.username)] = []
            by_user[(account.pk, account.username)].append(user_project.rights)
        by_role = [{"role": role, "users": users} for role, users in by_role.items()]
        by_user = [{"account": {"id": user[0], "username": user[1]}, "roles": roles} for user, roles in by_user.items()]
        return JsonResponse(constants.successful_data_json("Successfully fetched roles for project group", {"by_user": by_user, "by_role": by_role}))

    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project = Project.objects.filter(pk=id).first()
        project_group = project.project_group
        user = User.objects.filter(pk=request.data["id"]).first()
        if UserProjectGroup.objects.filter(account=user).filter(project_group=project_group).count() == 0:
            return JsonResponse(constants.error_json("That user is not in the correct project group"))
        user_roles_project = UserProject.objects.filter(project=project).filter(account=request.user).all()
        user_roles_project_group = UserProjectGroup.objects.filter(project_group=project_group).filter(account=request.user).all()
        all_rights = list(user_roles_project) + list(user_roles_project_group)
        max_rights = max([UserProject.role_hierarchy.index(x.rights) for x in all_rights]) if len(all_rights) > 0 else -1
        target_rights = UserProject.role_hierarchy.index(request.data["rights"])
        if target_rights > max_rights:
            return JsonResponse(constants.error_json("You do not have a high enough role to assign that role"))
        UserProject.objects.create(rights=request.data["rights"], account=user, project=project, colour=helpers.random_colour())
        return JsonResponse(constants.successful_empty_json("Successfully added user to project"))

    def delete(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        project = Project.objects.filter(pk=id).first()
        if request.data["id"] == request.user.pk:
            UserProject.objects.filter(account=request.user).filter(project=project).filter(rights=request.data["role"]).delete()
            return JsonResponse(constants.successful_empty_json("Successfully removed role"))
        if not security.user_has_access_to_project_with_security_level(request.user, project, ["O", "A"]):
            return JsonResponse(constants.no_access_json)

        project_group = project.project_group
        user_roles_project = UserProject.objects.filter(project=project).filter(account=request.user).all()
        user_roles_project_group = UserProjectGroup.objects.filter(project_group=project_group).filter(account=request.user).all()
        all_rights = list(user_roles_project) + list(user_roles_project_group)
        max_rights = max([UserProject.role_hierarchy.index(x.rights) for x in all_rights]) if len(all_rights) > 0 else -1
        target_rights = UserProject.role_hierarchy.index(request.data["rights"])
        if target_rights >= max_rights:
            return JsonResponse(constants.error_json("You do not have a high enough role to remove that role"))
        user = User.objects.filter(pk=request.data["id"]).first()
        UserProject.objects.filter(project=project).filter(account=user).delete()
        return JsonResponse(constants.successful_empty_json("Successfully removed user to project"))


class AssessmentCsvView(views.APIView):
    def post(self, request, id):
        if request.user.is_anonymous:
            return JsonResponse(constants.anonymous_json)
        group = ProjectGroup.objects.filter(pk=id).first()
        if not security.user_has_access_to_project_group_with_security_level(request.user, group, ["O", "A"]):
            return JsonResponse(constants.no_access_json)
        assessments = []
        for assessment_id in request.data["assessments"]:
            assessment_category = AssessmentCategory.objects.filter(pk=assessment_id).first()
            if assessment_category is None:
                return JsonResponse(constants.error_json(f"Assessment category with id {assessment_id} not found from this project group."))
            assessment_group = model_traversal.get_project_group_of_assessment_category(assessment_category)
            if group != assessment_group:
                return JsonResponse(constants.error_json(f"Assessment category with id {assessment_id} not found from this project group."))
            assessments.append(assessment_category)
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="assessment_data.csv"'},
        )
        writer = csv.writer(response)
        writer.writerow(["project", "developer"] + [str(x.pk) + ": " + x.name for x in assessments])
        for project in Project.objects.filter(project_group=group).all():
            for developer in UserProject.objects.filter(project=project).filter(disabled=False).filter(rights="M").all():
                row = [project.name, developer.account.username]
                for assessment in assessments:
                    if assessment.project_assessment:
                        assessment_instances = ProjectAssessment.objects.filter(project=project).filter(assessment_category=assessment).all()
                    else:
                        assessment_instances = UserAssessment.objects.filter(user_project=developer).filter(assessment_category=assessment).all()
                    assessment_types = [x.assessment_type for x in assessment_instances]
                    indexes = [UserAssessment.assessment_instance_hierarchy.index(x) for x in assessment_types]
                    target_index = indexes.index(max(indexes))
                    highest_priority_assessment = assessment_instances[target_index]
                    row.append(highest_priority_assessment.amount)
                    # print(f"Options were {assessment_types} and chose {highest_priority_assessment.assessment_type}")
                writer.writerow([str(x) for x in row])
        return response
