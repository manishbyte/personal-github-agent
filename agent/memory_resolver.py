from memory.redis import RedisMemory


async def resolve_memory(
    session_id: str,
    query: str,
):
    memory = RedisMemory()

    try:
        normalized_query = query.lower().strip()

        username = await memory.get_memory(
            session_id,
            "github_username",
        )

        profile = await memory.get_memory(
            session_id,
            "profile",
        )

        repository_owner = await memory.get_memory(
            session_id,
            "current_repository_owner",
        )

        repository_name = await memory.get_memory(
            session_id,
            "current_repository_name",
        )

        file_path = await memory.get_memory(
            session_id,
            "current_file_path",
        )

        username_queries = {
            "what is my username",
            "what's my username",
            "what is my github username",
            "what's my github username",
            "tell me my username",
            "show my username",
            "my username",
        }

        if normalized_query in username_queries:
            if username:
                return {
                    "handled": True,
                    "response": (
                        f"Your GitHub username is "
                        f"`{username}`."
                    ),
                }

        name_queries = {
            "what is my name",
            "what's my name",
            "tell me my name",
            "show my name",
        }

        if normalized_query in name_queries:
            if isinstance(profile, dict):
                name = profile.get("name")

                if name:
                    return {
                        "handled": True,
                        "response": (
                            f"Your GitHub profile name is "
                            f"`{name}`."
                        ),
                    }

        repository_queries = {
            "what repository are we working on",
            "which repository are we working on",
            "what repo are we working on",
            "which repo are we working on",
            "what is the current repository",
            "what is the current repo",
            "which repository is this",
            "which repo is this",
        }

        if normalized_query in repository_queries:
            if repository_name:

                if repository_owner:
                    repository = (
                        f"{repository_owner}/"
                        f"{repository_name}"
                    )
                else:
                    repository = repository_name

                return {
                    "handled": True,
                    "response": (
                        f"The current repository is "
                        f"`{repository}`."
                    ),
                }

        file_queries = {
            "what file are we working on",
            "which file are we working on",
            "what file did we analyze",
            "which file did we analyze",
            "what was the last file",
            "what is the current file",
            "which is the current file",
        }

        if normalized_query in file_queries:
            if file_path:
                return {
                    "handled": True,
                    "response": (
                        f"The current file is "
                        f"`{file_path}`."
                    ),
                }

        return {
            "handled": False,
        }

    finally:
        await memory.close()