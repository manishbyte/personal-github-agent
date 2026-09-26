from mcp import ClientSession


async def get_me(session: ClientSession):

    return await session.call_tool(

        "get_me",

        {},

    )


async def search_user_repositories(

    session: ClientSession,

    username: str,

):

    return await session.call_tool(

        "search_repositories",

        {

            "query": f"user:{username}",

        },

    )

async def get_file_contents(

    session: ClientSession,

    owner: str,

    repo: str,

    path: str,

):

    return await session.call_tool(

        "get_file_contents",

        {

            "owner": owner,

            "repo": repo,

            "path": path,

        },

    )


async def get_repository_structure(

    session: ClientSession,

    owner: str,

    repo: str,

    path: str = "/",

):

    return await session.call_tool(

        "get_file_contents",

        {

            "owner": owner,

            "repo": repo,

            "path": path,

        },

    )


async def create_issue(

    session: ClientSession,

    owner: str,

    repo: str,

    title: str,

    body: str,

):

    return await session.call_tool(

        "issue_write",

        {

            "method": "create",

            "owner": owner,

            "repo": repo,

            "title": title,

            "body": body,

        },

    )