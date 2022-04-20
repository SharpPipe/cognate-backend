
from .serializers import TimeSpentSerializer


def serialize_time_spent(times_spent):
    return_json = []
    for time_spent in times_spent:
        dat = TimeSpentSerializer(time_spent).data
        dat["title"] = dat["issue"]["title"]
        dat["gitlab_link"] = dat["issue"]["gitlab_link"]
        del dat["issue"]
        dat["repo_id"] = -1
        if time_spent.issue.repository is not None:
            dat["repo_id"] = time_spent.issue.repository.pk
        elif time_spent.issue.milestone is not None:
            if time_spent.issue.milestone.repository is not None:
                dat["repo_id"] = time_spent.issue.milestone.repository.pk

        return_json.append(dat)
    return return_json
