from typing import Any
from typing_extensions import TypedDict, Annotated

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):

    # ========================================================
    # CONVERSATION
    # ========================================================

    messages: Annotated[list, add_messages]

    user_query: str

    # ========================================================
    # MEMORY ROUTING
    # ========================================================

    memory_handled: bool

    direct_response: str

    session_id: str

    # ========================================================
    # INTENT
    # ========================================================

    intent: str

    # ========================================================
    # GITHUB USER
    # ========================================================

    github_username: str

    github_access_token: str

    profile: dict[str, Any]

    # ========================================================
    # REPOSITORIES
    # ========================================================

    repositories: list[dict[str, Any]]

    repository_owner: str

    repository_name: str

    # ========================================================
    # FILE
    # ========================================================

    requested_file: str

    file_path: str

    file_content: str

    # ========================================================
    # REPOSITORY STRUCTURE
    # ========================================================

    repository_structure: list[dict[str, Any]]

    # ========================================================
    # FILE ANALYSIS
    # ========================================================

    analysis_result: dict[str, Any]

    # ========================================================
    # ISSUE
    # ========================================================

    issue_title: str

    issue_body: str

    issue_repository_owner: str

    issue_repository_name: str

    issue_proposal: dict[str, Any]

    issue_approved: bool

    issue_number: int

    issue_url: str

    issue_error: str

    # ========================================================
    # RESPONSE
    # ========================================================

    response: str

    error: str