anonymous_json = {"Error": "Not logged in."}
no_access_json = {"Error": "You don't have access"}


def successful_empty_json(message):
    return {
        "success": "true",
        "message": message,
        "data": {}
    }
