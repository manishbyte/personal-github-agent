import json
from typing import Any


def extract_text(response: Any) -> str | None:

    content = getattr(response, "content", None)

    if not content:
        return None

    for item in content:

        if getattr(item, "type", None) != "text":
            continue

        text = getattr(item, "text", None)

        if isinstance(text, str):
            return text

    return None


def extract_json(response: Any) -> Any:

    text = extract_text(response)

    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def extract_username(response: Any) -> str | None:

    data = extract_json(response)

    if isinstance(data, dict):
        return data.get("login")

    return None


def extract_repositories(response: Any) -> list[dict]:

    data = extract_json(response)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        items = data.get("items")

        if isinstance(items, list):
            return items

    return []


def extract_file_content(response: Any) -> str | None:

    content = getattr(response, "content", None)

    if not content:
        return None

    # Actual file content is normally inside EmbeddedResource
    for item in content:

        if getattr(item, "type", None) != "resource":
            continue

        resource = getattr(item, "resource", None)

        if resource is None:
            continue

        text = getattr(resource, "text", None)

        if isinstance(text, str):
            return text

    # Fallback to text content
    for item in content:

        if getattr(item, "type", None) != "text":
            continue

        text = getattr(item, "text", None)

        if not text:
            continue

        if text.startswith("successfully downloaded text file"):
            continue

        return text

    return None

def extract_repository_structure(response: Any) -> list[dict]:

    content = getattr(response, "content", None)

    if not content:
        return []

    for item in content:

        if getattr(item, "type", None) != "text":
            continue

        text = getattr(item, "text", None)

        if not isinstance(text, str):
            continue

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue

        if isinstance(data, list):
            return data

        if isinstance(data, dict):

            items = data.get("items")

            if isinstance(items, list):
                return items

    return []


def extract_directory_items(response: Any) -> list[dict]:

    data = extract_json(response)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        items = data.get("items")

        if isinstance(items, list):
            return items

    return []