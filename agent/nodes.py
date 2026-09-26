import json
import re

from github_mcp.url_parser import parse_github_url
from github_mcp.file_utils import normalize_requested_file

from agent.state import AgentState
from agent.memory_resolver import resolve_memory

from github_mcp.client import GitHubMCPClient
from github_mcp.tools import (
    get_me,
    search_user_repositories,
    get_file_contents,
    get_repository_structure,
)

from github_mcp.parsers import (
    extract_json,
    extract_username,
    extract_repositories,
    extract_file_content,
    extract_directory_items,
)

from llm.models import get_llm


# ============================================================
# GLOBAL CLIENT
# ============================================================

github_client = GitHubMCPClient()
llm = get_llm()


# ============================================================
# MEMORY NODE
# ============================================================

async def memory_node(state: AgentState):

    query = state.get(
        "user_query",
        "",
    )

    # --------------------------------------------------------
    # Current session
    # --------------------------------------------------------

    session_id = "github-chat"

    # --------------------------------------------------------
    # Ask Redis memory resolver
    # --------------------------------------------------------

    result = await resolve_memory(
        session_id,
        query,
    )

    # --------------------------------------------------------
    # Redis handled the request
    # --------------------------------------------------------

    if result.get("handled"):

        return {
            "memory_handled": True,
            "direct_response": result.get(
                "response",
                "",
            ),
        }

    # --------------------------------------------------------
    # Redis could not answer
    # Continue to intent
    # --------------------------------------------------------

    return {
        "memory_handled": False,
    }


# ============================================================
# GITHUB URL EXTRACTION
# ============================================================

def extract_github_url(
    query: str,
) -> str | None:

    pattern = (
        r"https?://(?:www\.)?"
        r"github\.com/"
        r"[A-Za-z0-9_.-]+/"
        r"[A-Za-z0-9_.-]+"
    )

    match = re.search(
        pattern,
        query,
        re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(0)


# ============================================================
# REQUESTED FILE EXTRACTION
# ============================================================

def extract_requested_file(
    query: str,
) -> str | None:

    patterns = [

        # Example:
        # analyze `planner.py` file
        r"(?:analyze|analyse|inspect|read|review|open)"
        r"\s+(?:the\s+)?`([^`]+)`\s+file",

        # Example:
        # analyze planner.py file
        # analyze planner file
        r"(?:analyze|analyse|inspect|read|review|open)"
        r"\s+(?:the\s+)?([A-Za-z0-9_.\-/]+)"
        r"\s+file",

        # Example:
        # file is `planner.py`
        r"(?:file|filename)\s+"
        r"(?:is\s+)?`([^`]+)`",

        # Example:
        # file is planner.py
        r"(?:file|filename)\s+"
        r"(?:is\s+)?([A-Za-z0-9_.\-/]+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            query,
            re.IGNORECASE,
        )

        if match:

            file_name = match.group(1)

            return normalize_requested_file(
                file_name
            )

    return None


# ============================================================
# DIRECT FILE REQUEST DETECTION
# ============================================================

def extract_direct_file_request(
    query: str,
):
    """
    Detect requests such as:

    Analyze planner file in
    https://github.com/owner/repository

    Returns:

    {
        "repository_owner": "...",
        "repository_name": "...",
        "requested_file": "..."
    }

    or None.
    """

    github_url = extract_github_url(
        query
    )

    if not github_url:
        return None

    requested_file = extract_requested_file(
        query
    )

    if not requested_file:
        return None

    owner, repository = parse_github_url(
        github_url
    )

    if not owner or not repository:
        return None

    return {
        "repository_owner": owner,
        "repository_name": repository,
        "requested_file": requested_file,
    }


# ============================================================
# DIRECT STRUCTURE REQUEST DETECTION
# ============================================================

def extract_direct_structure_request(
    query: str,
):

    structure_keywords = [
        "file structure",
        "repository structure",
        "repo structure",
        "folder structure",
        "directory structure",
        "file tree",
        "repo tree",
        "repository tree",
        "list files",
        "show files",
        "show me the files",
        "files and folders",
    ]

    normalized_query = query.lower()

    if not any(
        keyword in normalized_query
        for keyword in structure_keywords
    ):
        return None

    github_url = extract_github_url(query)

    if not github_url:
        return None

    owner, repository = parse_github_url(
        github_url
    )

    if not owner or not repository:
        return None

    return {
        "repository_owner": owner,
        "repository_name": repository,
    }


# ============================================================
# FILE MATCHING
# ============================================================

def file_matches(
    path: str,
    requested_file: str,
) -> bool:

    path = path.replace(
        "\\",
        "/",
    )

    requested_file = requested_file.replace(
        "\\",
        "/",
    )

    path = path.strip("/")
    requested_file = requested_file.strip("/")

    # --------------------------------------------------------
    # Exact full path
    # --------------------------------------------------------

    if path.lower() == requested_file.lower():

        return True

    file_name = path.split("/")[-1]

    requested_name = (
        requested_file.split("/")[-1]
    )

    # --------------------------------------------------------
    # Exact filename
    # --------------------------------------------------------

    if file_name.lower() == requested_name.lower():

        return True

    # --------------------------------------------------------
    # Filename without extension
    #
    # Example:
    #
    # planner
    #
    # matches:
    #
    # planner.py
    # planner.js
    # planner.ts
    # --------------------------------------------------------

    if "." not in requested_name:

        if "." in file_name:

            file_stem = file_name.rsplit(
                ".",
                1,
            )[0]

        else:

            file_stem = file_name

        if (
            file_stem.lower()
            == requested_name.lower()
        ):

            return True

    return False


# ============================================================
# FIND FILE MATCHES
# ============================================================

def find_file_matches(
    items: list[dict],
    requested_file: str,
) -> list[str]:

    matches = []

    for item in items:

        item_type = item.get(
            "type"
        )

        item_path = item.get(
            "path",
            "",
        )

        # ----------------------------------------------------
        # FILE
        # ----------------------------------------------------

        if item_type == "file":

            if file_matches(
                item_path,
                requested_file,
            ):

                matches.append(
                    item_path
                )

        # ----------------------------------------------------
        # DIRECTORY
        # ----------------------------------------------------

        elif item_type in {
            "dir",
            "directory",
        }:

            children = item.get(
                "children",
                [],
            )

            matches.extend(
                find_file_matches(
                    children,
                    requested_file,
                )
            )

    return matches


# ============================================================
# INTENT NODE
# ============================================================


async def intent_node(state: AgentState):

    query = state["user_query"]

    # ========================================================
    # DIRECT GITHUB URL + FILE REQUEST
    # ========================================================

    direct_file_request = (
        extract_direct_file_request(
            query
        )
    )

    if direct_file_request:

        return {
            "intent": "file_content",
            "repository_owner": (
                direct_file_request[
                    "repository_owner"
                ]
            ),
            "repository_name": (
                direct_file_request[
                    "repository_name"
                ]
            ),
            "requested_file": (
                direct_file_request[
                    "requested_file"
                ]
            ),
            "file_path": (
                direct_file_request[
                    "requested_file"
                ]
            ),
        }

    # ========================================================
    # DIRECT GITHUB URL + STRUCTURE REQUEST
    # ========================================================

    direct_structure_request = (
        extract_direct_structure_request(
            query
        )
    )

    if direct_structure_request:

        return {
            "intent": "structure",
            "repository_owner": (
                direct_structure_request[
                    "repository_owner"
                ]
            ),
            "repository_name": (
                direct_structure_request[
                    "repository_name"
                ]
            ),
            "requested_file": None,
            "file_path": None,
        }

    # --------------------------------------------------------
    # Get recent conversation history
    # --------------------------------------------------------

    messages = state.get(
        "messages",
        [],
    )

    history_lines = []

    for message in messages[-10:]:

        role = getattr(
            message,
            "type",
            "unknown",
        )

        content = getattr(
            message,
            "content",
            "",
        )

        if isinstance(
            content,
            str,
        ):

            history_lines.append(
                f"{role}: {content}"
            )

    history = "\n".join(
        history_lines
    )

    # ========================================================
    # INTENT PROMPT
    # ========================================================

    prompt = f"""
You are the intent and context extraction component of a GitHub assistant.

Your job is to understand the CURRENT user request using the recent
conversation history when necessary.

CURRENT USER QUERY:
{query}

RECENT CONVERSATION:
{history}

--------------------------------------------------
SUPPORTED INTENTS
--------------------------------------------------

Choose exactly one:

- profile
- repositories
- file_content
- file_analysis
- analyze_and_create_issue
- create_issue
- structure
- unknown

--------------------------------------------------
INTENT MEANINGS
--------------------------------------------------

- profile:
  The user wants information about their GitHub profile.

- repositories:
  The user wants to list or inspect their repositories.

- file_content:
  The user wants to see or read the actual file content.

- file_analysis:
  The user wants the file analyzed, reviewed, inspected, or wants
  problems, bugs, or potential issues explained.

  This is analysis only. Do NOT interpret this as a request to create
  a GitHub issue.

- analyze_and_create_issue:
  The user explicitly asks to analyze, review, or inspect a file AND
  create a GitHub issue as part of that request.

  This intent covers BOTH mandatory and conditional issue creation.

  Mandatory creation:
  The user directly commands issue creation, regardless of whether
  the analysis identifies a concrete problem.

  Examples:
  - "Analyze this file and create an issue."
  - "Analyze this file and create an issue even if there is no bug."
  - "Review auth.py and open a GitHub issue."

  Conditional creation:
  The user asks for an issue only if the analysis identifies a problem,
  bug, defect, or actionable improvement.

  Examples:
  - "Analyze this file and create an issue if you find a bug."
  - "If you think there is a problem, create an issue."
  - "Create an issue only if you find a concrete problem."

  Preserve the distinction between mandatory and conditional creation
  in the original user query. The issue proposal node uses that request
  to decide whether an issue should be proposed.

- create_issue:
  The user asks to create a GitHub issue for a previously identified
  problem or an issue whose details are already established in the
  conversation, without requesting a new file analysis.

--------------------------------------------------
IMPORTANT RULES
--------------------------------------------------

1. The word "issue", "problem", or "bug" by itself does NOT mean
   the user wants a GitHub issue created.

2. Resolve references to previous conversation context when appropriate.

3. A request to analyze a file and create an issue must use
   analyze_and_create_issue, regardless of whether creation is
   mandatory or conditional.

4. A request to analyze a file without asking for issue creation
   must use file_analysis.

5. A request to create an issue for a previously identified problem,
   without requesting a new file analysis, must use create_issue.

6. Do not invent a repository owner, repository name, file path,
   or issue number.

--------------------------------------------------
IMPORTANT CONTEXT RULES
--------------------------------------------------

1. The user may refer to previous information using words such as:

   - it
   - its
   - that repo
   - that repository
   - this repo
   - previous repo
   - that file
   - this file
   - the file
   - same repository

2. Resolve these references using the conversation history.

3. If the user explicitly provides a repository in the form:

   owner/repository

   extract both:

   repository_owner = owner
   repository_name = repository

4. If the user explicitly provides a GitHub repository URL:

   https://github.com/owner/repository

   extract:

   repository_owner = owner
   repository_name = repository

5. If the user only provides a repository name and the conversation
   already contains its owner, use the previous owner.

6. If the user only provides a repository name and no owner is known,
   set repository_owner to null.

7. Do NOT invent a repository owner.

8. If the user asks about a file and gives only a filename, preserve
   only the filename.

   Example:
   "analyze research.py"

   requested_file = "research.py"

9. If the user says:

   "analyze research file"

   preserve:

   requested_file = "research"

10. If the user gives a full path, preserve the full path exactly.

    Example:
    "analyze nodes/research.py"

    requested_file = "nodes/research.py"

11. Do NOT guess the directory of a filename.

12. The application will search the repository tree to resolve
    the actual file path.

13. Normalize README references:

    "readme"
    "README"
    "readme file"

    -> README.md

14. Do NOT invent a file path.

15. For structure requests, file_path must be null.

16. For profile requests, repository_owner, repository_name,
    requested_file, and file_path should normally be null.

17. For repositories requests, repository_owner, repository_name,
    requested_file, and file_path should normally be null.

--------------------------------------------------
EXAMPLES
--------------------------------------------------

Example 1:

Current query:
"show readme file from ecommerce"

Output:
{{
    "intent": "file_content",
    "repository_owner": "manishbyte",
    "repository_name": "ecommerce",
    "requested_file": "README.md",
    "file_path": "README.md"
}}

Example 2:

Current query:
"show src/main.py from ecommerce"

Output:
{{
    "intent": "file_content",
    "repository_owner": "manishbyte",
    "repository_name": "ecommerce",
    "requested_file": "src/main.py",
    "file_path": "src/main.py"
}}

Example 3:

Current query:
"analyze research.py from ai-blog-generator"

Output:
{{
    "intent": "file_analysis",
    "repository_owner": "manishbyte",
    "repository_name": "ai-blog-generator",
    "requested_file": "research.py",
    "file_path": "research.py"
}}

Example 4: Mandatory issue creation

Current query:
"analyze research.py from ai-blog-generator and create an issue"

Output:
{{
    "intent": "analyze_and_create_issue",
    "repository_owner": "manishbyte",
    "repository_name": "ai-blog-generator",
    "requested_file": "research.py",
    "file_path": "research.py"
}}

Example 5: Mandatory creation even without a bug

Current query:
"analyze research.py from ai-blog-generator and create an issue even if no bug exists"

Output:
{{
    "intent": "analyze_and_create_issue",
    "repository_owner": "manishbyte",
    "repository_name": "ai-blog-generator",
    "requested_file": "research.py",
    "file_path": "research.py"
}}

Example 6: Conditional issue creation

Current query:
"analyze research.py from ai-blog-generator and create an issue only if you find a bug"

Output:
{{
    "intent": "analyze_and_create_issue",
    "repository_owner": "manishbyte",
    "repository_name": "ai-blog-generator",
    "requested_file": "research.py",
    "file_path": "research.py"
}}

Example 7:

Current query:
"create a GitHub issue for the problem we found in research.py"

Output:
{{
    "intent": "create_issue",
    "repository_owner": "manishbyte",
    "repository_name": "ai-blog-generator",
    "requested_file": "research.py",
    "file_path": "research.py"
}}

Example 8:

Previous conversation:
User: Analyze research.py from ai-blog-generator
Assistant: The analysis found a potential authentication bug.

Current query:
"create an issue for this"

Output:
{{
    "intent": "create_issue",
    "repository_owner": "manishbyte",
    "repository_name": "ai-blog-generator",
    "requested_file": "research.py",
    "file_path": "research.py"
}}

Example 9:

Previous conversation:
User: Analyze openai/openai-python

Current query:
"show its structure"

Output:
{{
    "intent": "structure",
    "repository_owner": "openai",
    "repository_name": "openai-python",
    "requested_file": null,
    "file_path": null
}}

Example 10:

Previous conversation:
User: Analyze openai/openai-python

Current query:
"analyze _client.py"

Output:
{{
    "intent": "file_analysis",
    "repository_owner": "openai",
    "repository_name": "openai-python",
    "requested_file": "_client.py",
    "file_path": "_client.py"
}}

Example 11:

Previous conversation:
User: Analyze openai/openai-python
Assistant: The file is src/openai/_client.py.

Current query:
"what does that file do?"

Output:
{{
    "intent": "file_content",
    "repository_owner": "openai",
    "repository_name": "openai-python",
    "requested_file": null,
    "file_path": null
}}

--------------------------------------------------
OUTPUT
--------------------------------------------------

Return ONLY valid JSON.

The JSON must have exactly these fields:

{{
    "intent": "...",
    "repository_owner": "...",
    "repository_name": "...",
    "requested_file": "...",
    "file_path": "..."
}}

Use null when a value is unknown or not applicable.
"""

    # ========================================================
    # CALL LLM
    # ========================================================

    response = await llm.ainvoke(
        prompt
    )

    # ========================================================
    # PARSE JSON
    # ========================================================

    content = response.content

    if isinstance(
        content,
        list,
    ):

        content = "".join(
            item.get("text", "")
            for item in content
            if isinstance(
                item,
                dict,
            )
        )

    content = content.strip()

    # --------------------------------------------------------
    # Remove markdown JSON fences
    # --------------------------------------------------------

    if content.startswith("```"):

        content = content.replace(
            "```json",
            "",
            1,
        )

        content = content.replace(
            "```",
            "",
            1,
        )

        content = content.strip()

    try:

        data = json.loads(
            content
        )

    except json.JSONDecodeError:

        return {
            "intent": "unknown",
            "repository_owner": None,
            "repository_name": None,
            "requested_file": None,
            "file_path": None,
            "error": (
                "Could not understand "
                "the request."
            ),
        }

    requested_file = data.get(
        "requested_file"
    )

    file_path = data.get(
        "file_path"
    )

    # --------------------------------------------------------
    # Normalize requested file
    # --------------------------------------------------------

    if requested_file:

        requested_file = (
            normalize_requested_file(
                requested_file
            )
        )

    # --------------------------------------------------------
    # Normalize file path
    # --------------------------------------------------------

    if file_path:

        file_path = (
            normalize_requested_file(
                file_path
            )
        )

    # --------------------------------------------------------
    # README normalization
    # --------------------------------------------------------

    if requested_file and requested_file.lower() in {
        "readme",
        "readme file",
        "the readme",
        "the readme file",
    }:

        requested_file = "README.md"

    if file_path and file_path.lower() in {
        "readme",
        "readme file",
        "the readme",
        "the readme file",
    }:

        file_path = "README.md"

    return {
        "intent": data.get(
            "intent",
            "unknown",
        ),
        "repository_owner": data.get(
            "repository_owner"
        ),
        "repository_name": data.get(
            "repository_name"
        ),
        "requested_file": requested_file,
        "file_path": file_path,
    }



# ============================================================
# PROFILE NODE
# ============================================================

async def profile_node(state: AgentState):

    github_client = GitHubMCPClient(
        access_token=state["github_access_token"]
    )

    session = await github_client.connect()

    try:

        result = await get_me(
            session
        )

        # ----------------------------------------------------
        # Extract complete GitHub profile
        # ----------------------------------------------------

        profile = extract_json(
            result
        )

        if not isinstance(
            profile,
            dict,
        ):

            return {
                "error": (
                    "Could not retrieve "
                    "GitHub profile information."
                )
            }

        # ----------------------------------------------------
        # Extract username
        # ----------------------------------------------------

        username = profile.get(
            "login"
        )

        if not username:

            return {
                "error": (
                    "Could not determine "
                    "GitHub username."
                )
            }

        # ----------------------------------------------------
        # Return complete profile
        # ----------------------------------------------------

        return {
            "github_username": username,
            "profile": profile,
        }

    finally:

        await github_client.close()


# ============================================================
# REPOSITORY NODE
# ============================================================

async def repository_node(
    state: AgentState,
):  


    github_client = GitHubMCPClient(
        access_token=state["github_access_token"]
    )

    session = await github_client.connect()

    try:

        username = state.get(
            "github_username"
        )

        if not username:

            me = await get_me(
                session
            )

            username = extract_username(
                me
            )

        if not username:

            return {
                "error": (
                    "Could not determine "
                    "GitHub username."
                )
            }

        result = await search_user_repositories(
            session,
            username,
        )

        repositories = extract_repositories(
            result
        )

        return {
            "github_username": username,
            "repositories": repositories,
        }

    finally:

        await github_client.close()


# ============================================================
# FILE CONTENT NODE
# ============================================================

async def file_content_node(
    state: AgentState,
):

    repository_name = state.get(
        "repository_name"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # requested_file = what user asked for
    #
    # file_path = actual resolved GitHub path
    # --------------------------------------------------------

    requested_path = state.get(
        "requested_file"
    )

    if not requested_path:

        requested_path = state.get(
            "file_path"
        )

    if not repository_name:

        return {
            "error": (
                "Please provide the "
                "repository name."
            )
        }

    if not requested_path:

        return {
            "error": (
                "Please provide the "
                "file name."
            )
        }

    # --------------------------------------------------------
    # Defensive README normalization
    # --------------------------------------------------------

    if requested_path.lower() in {
        "readme",
        "readme file",
        "the readme",
        "the readme file",
    }:

        requested_path = "README.md"

    # --------------------------------------------------------
    # Normalize requested filename/path
    # --------------------------------------------------------

    requested_path = (
        normalize_requested_file(
            requested_path
        )
    )

    github_client = GitHubMCPClient(
        access_token=state["github_access_token"]
    )

    session = await github_client.connect()

    try:

        # ====================================================
        # GET GITHUB USERNAME
        # ====================================================

        username = state.get(
            "github_username"
        )

        if not username:

            me = await get_me(
                session
            )

            username = extract_username(
                me
            )

        if not username:

            return {
                "error": (
                    "Could not determine "
                    "GitHub username."
                )
            }

        # ====================================================
        # DETERMINE REPOSITORY OWNER
        # ====================================================

        owner = (
            state.get(
                "repository_owner"
            )
            or username
        )

        # ====================================================
        # BUILD REPOSITORY TREE
        # ====================================================

        MAX_DEPTH = 10
        MAX_FILES = 1000

        file_count = 0

        def normalize_path(
            path: str,
        ) -> str:

            if not path or path == "/":

                return "/"

            path = path.strip()

            if not path.startswith("/"):

                path = "/" + path

            return path

        async def build_tree(
            path: str = "/",
            depth: int = 0,
        ):

            nonlocal file_count

            if depth > MAX_DEPTH:

                return []

            if file_count >= MAX_FILES:

                return []

            current_path = normalize_path(
                path
            )

            result = await get_repository_structure(
                session,
                owner=owner,
                repo=repository_name,
                path=current_path,
            )

            items = extract_directory_items(
                result
            )

            tree = []

            for item in items:

                if file_count >= MAX_FILES:

                    break

                item_name = item.get(
                    "name"
                )

                item_type = item.get(
                    "type"
                )

                if not item_name:

                    continue

                item_path = item.get(
                    "path"
                )

                if not item_path:

                    if current_path == "/":

                        item_path = item_name

                    else:

                        item_path = (
                            f"{current_path.rstrip('/')}"
                            f"/{item_name}"
                        )

                item_path = normalize_path(
                    item_path
                )

                # ------------------------------------------------
                # DIRECTORY
                # ------------------------------------------------

                if item_type in {
                    "dir",
                    "directory",
                }:

                    children = await build_tree(
                        path=item_path,
                        depth=depth + 1,
                    )

                    tree.append({
                        "name": item_name,
                        "type": "directory",
                        "path": item_path,
                        "children": children,
                    })

                # ------------------------------------------------
                # FILE
                # ------------------------------------------------

                else:

                    file_count += 1

                    tree.append({
                        "name": item_name,
                        "type": "file",
                        "path": item_path,
                    })

            return tree

        structure = await build_tree(
            path="/",
            depth=0,
        )

        # ====================================================
        # FIND ALL MATCHING FILES
        # ====================================================

        matches = find_file_matches(
            structure,
            requested_path,
        )

        # ====================================================
        # FILE NOT FOUND
        # ====================================================

        if not matches:

            return {
                "error": (
                    f"Could not find "
                    f"`{requested_path}` "
                    f"in repository "
                    f"`{repository_name}`."
                ),
                "repository_owner": owner,
                "repository_name": repository_name,
                "requested_file": requested_path,
                "file_path": requested_path,
            }

        # ====================================================
        # MULTIPLE MATCHES
        # ====================================================

        if len(matches) > 1:

            matches_text = "\n".join(
                f"{index}. `{path}`"
                for index, path in enumerate(
                    matches,
                    start=1,
                )
            )

            return {
                "error": (
                    f"I found multiple files "
                    f"matching `{requested_path}` "
                    f"in `{owner}/{repository_name}`:\n\n"
                    f"{matches_text}\n\n"
                    "Please tell me which file "
                    "you want me to analyze."
                ),
                "repository_owner": owner,
                "repository_name": repository_name,
                "requested_file": requested_path,
                "file_path": None,
            }

        # ====================================================
        # EXACTLY ONE MATCH
        # ====================================================

        resolved_path = matches[0]

        # ====================================================
        # GET ACTUAL FILE CONTENT
        # ====================================================

        result = await get_file_contents(
            session,
            owner=owner,
            repo=repository_name,
            path=resolved_path,
        )

        content = extract_file_content(
            result
        )

        if content is None:

            return {
                "error": (
                    f"Could not read "
                    f"`{resolved_path}` "
                    f"from "
                    f"`{repository_name}`."
                ),
                "repository_owner": owner,
                "repository_name": repository_name,
                "requested_file": requested_path,
                "file_path": resolved_path,
            }

        # ====================================================
        # RETURN FILE INFORMATION
        # ====================================================

        return {
            "github_username": username,
            "repository_owner": owner,
            "repository_name": repository_name,
            "requested_file": requested_path,
            "file_path": resolved_path,
            "file_content": content,
        }

    finally:

        await github_client.close()


# ============================================================
# REPOSITORY STRUCTURE NODE
# ============================================================

async def repository_structure_node(
    state: AgentState,
):

    repository_name = state.get(
        "repository_name"
    )

    if not repository_name:

        return {
            "error": (
                "Please provide the "
                "repository name."
            )
        }
     
    github_client = GitHubMCPClient(
        access_token=state["github_access_token"]
    )

    session = await github_client.connect()

    try:

        username = state.get(
            "github_username"
        )

        if not username:

            me = await get_me(
                session
            )

            username = extract_username(
                me
            )

        if not username:

            return {
                "error": (
                    "Could not determine "
                    "GitHub username."
                )
            }

        # ----------------------------------------------------
        # DETERMINE REPOSITORY OWNER
        # ----------------------------------------------------

        owner = (
            state.get(
                "repository_owner"
            )
            or username
        )

        # ----------------------------------------------------
        # Safety limits
        # ----------------------------------------------------

        MAX_DEPTH = 10
        MAX_FILES = 1000

        file_count = 0

        # ----------------------------------------------------
        # Normalize repository paths
        # ----------------------------------------------------

        def normalize_path(
            path: str,
        ) -> str:

            if not path or path == "/":

                return "/"

            path = path.strip()

            if not path.startswith("/"):

                path = "/" + path

            return path

        # ----------------------------------------------------
        # Recursive tree builder
        # ----------------------------------------------------

        async def build_tree(
            path: str = "/",
            depth: int = 0,
        ):

            nonlocal file_count

            # Depth protection
            if depth > MAX_DEPTH:

                return [
                    {
                        "name": "...",
                        "type": "limit",
                        "path": path,
                    }
                ]

            # File-count protection
            if file_count >= MAX_FILES:

                return [
                    {
                        "name": "...",
                        "type": "limit",
                        "path": path,
                    }
                ]

            current_path = normalize_path(
                path
            )

            print(
                f"Reading repository path: "
                f"{current_path}"
            )

            # ------------------------------------------------
            # Get directory contents
            # ------------------------------------------------

            result = await get_repository_structure(
                session,
                owner=owner,
                repo=repository_name,
                path=current_path,
            )

            # ------------------------------------------------
            # Parse directory contents
            # ------------------------------------------------

            items = extract_directory_items(
                result
            )

            tree = []

            # ------------------------------------------------
            # Process every item
            # ------------------------------------------------

            for item in items:

                if file_count >= MAX_FILES:

                    tree.append({
                        "name": "...",
                        "type": "limit",
                        "path": current_path,
                    })

                    break

                item_name = item.get(
                    "name"
                )

                item_type = item.get(
                    "type"
                )

                if not item_name:

                    continue

                # --------------------------------------------
                # Get path returned by GitHub MCP
                # --------------------------------------------

                item_path = item.get(
                    "path"
                )

                if not item_path:

                    if current_path == "/":

                        item_path = item_name

                    else:

                        item_path = (
                            f"{current_path.rstrip('/')}"
                            f"/{item_name}"
                        )

                item_path = normalize_path(
                    item_path
                )

                # --------------------------------------------
                # DIRECTORY
                # --------------------------------------------

                if item_type in {
                    "dir",
                    "directory",
                }:

                    children = await build_tree(
                        path=item_path,
                        depth=depth + 1,
                    )

                    tree.append({
                        "name": item_name,
                        "type": "directory",
                        "path": item_path,
                        "children": children,
                    })

                # --------------------------------------------
                # FILE
                # --------------------------------------------

                else:

                    file_count += 1

                    tree.append({
                        "name": item_name,
                        "type": "file",
                        "path": item_path,
                    })

            return tree

        # ----------------------------------------------------
        # Start from repository ROOT
        # ----------------------------------------------------

        structure = await build_tree(
            path="/",
            depth=0,
        )

        # ----------------------------------------------------
        # Empty repository
        # ----------------------------------------------------

        if not structure:

            return {
                "error": (
                    f"No files or folders were found "
                    f"in `{repository_name}`."
                )
            }

        # ----------------------------------------------------
        # Return recursive structure
        # ----------------------------------------------------

        return {
            "github_username": username,
            "repository_owner": owner,
            "repository_name": repository_name,
            "repository_structure": structure,
        }

    finally:

        await github_client.close()


# ============================================================
# ROUTER
# ============================================================

def route_intent(
    state: AgentState,
):

    intent = state.get(
        "intent"
    )

    if intent == "profile":

        return "profile"

    if intent == "repositories":

        return "repositories"

    if intent == "file_content":

        return "file_content"

    if intent == "create_issue":

        return "issue_proposal"

    if intent in {
        "file_analysis",
        "analyze_and_create_issue",
    }:

        return "file_content"

    if intent == "structure":

        return "structure"

    return "response"


# ============================================================
# RESPONSE NODE
# ============================================================

async def response_node(
    state: AgentState,
):

    # --------------------------------------------------------
    # Current request
    # --------------------------------------------------------

    user_query = state.get(
        "user_query",
        "",
    )

    # --------------------------------------------------------
    # Conversation history
    # --------------------------------------------------------

    messages = state.get(
        "messages",
        [],
    )

    history_lines = []

    for message in messages[-10:]:

        role = getattr(
            message,
            "type",
            "unknown",
        )

        content = getattr(
            message,
            "content",
            "",
        )

        if isinstance(
            content,
            str,
        ):

            history_lines.append(
                f"{role}: {content}"
            )

    history = "\n".join(
        history_lines
    )

    # --------------------------------------------------------
    # GitHub data collected by previous nodes
    # --------------------------------------------------------

    intent = state.get(
        "intent"
    )

    username = state.get(
        "github_username"
    )

    # Complete GitHub profile
    profile = state.get(
        "profile",
        {},
    )

    repositories = state.get(
        "repositories",
        [],
    )

    repository_owner = state.get(
        "repository_owner"
    )

    repository_name = state.get(
        "repository_name"
    )

    requested_file = state.get(
        "requested_file"
    )

    file_path = state.get(
        "file_path"
    )

    file_content = state.get(
        "file_content"
    )

    repository_structure = state.get(
        "repository_structure",
        [],
    )

    error = state.get(
        "error"
    )

    # --------------------------------------------------------
    # Prepare profile information
    # --------------------------------------------------------

    profile_text = ""

    if profile:

        profile_text = json.dumps(
            profile,
            indent=2,
            default=str,
        )

    # --------------------------------------------------------
    # Prepare repository information
    # --------------------------------------------------------

    repositories_text = ""

    if repositories:

        repositories_text = json.dumps(
            repositories,
            indent=2,
            default=str,
        )

    # --------------------------------------------------------
    # Prepare repository structure
    # --------------------------------------------------------

    structure_text = ""

    if repository_structure:

        structure_text = json.dumps(
            repository_structure,
            indent=2,
            default=str,
        )

    # --------------------------------------------------------
    # Prepare file content
    # --------------------------------------------------------

    file_content_text = (
        file_content
        or ""
    )

    # --------------------------------------------------------
    # Final response prompt
    # --------------------------------------------------------

    prompt = f"""
You are a helpful Personal GitHub Agent.

Answer the user's CURRENT question using:

1. The current GitHub data collected by the agent.
2. The recent conversation history when needed.
3. The current intent.

Do not invent GitHub information.

--------------------------------------------------
CURRENT USER QUERY
--------------------------------------------------

{user_query}

--------------------------------------------------
RECENT CONVERSATION
--------------------------------------------------

{history}

--------------------------------------------------
CURRENT INTENT
--------------------------------------------------

{intent}

--------------------------------------------------
AUTHENTICATED GITHUB USERNAME
--------------------------------------------------

{username}

--------------------------------------------------
GITHUB PROFILE
--------------------------------------------------

{profile_text}

--------------------------------------------------
REPOSITORY OWNER
--------------------------------------------------

{repository_owner}

--------------------------------------------------
REPOSITORY NAME
--------------------------------------------------

{repository_name}

--------------------------------------------------
REQUESTED FILE
--------------------------------------------------

{requested_file}

--------------------------------------------------
RESOLVED FILE PATH
--------------------------------------------------

{file_path}

--------------------------------------------------
REPOSITORIES
--------------------------------------------------

{repositories_text}

--------------------------------------------------
FILE CONTENT
--------------------------------------------------

{file_content_text}

--------------------------------------------------
REPOSITORY STRUCTURE
--------------------------------------------------

{structure_text}

--------------------------------------------------
ERROR
--------------------------------------------------

{error}

--------------------------------------------------
RESPONSE RULES
--------------------------------------------------

1. Answer the CURRENT user question directly.

2. Use conversation history to understand references such as:

   - it
   - its
   - that repository
   - this repository
   - that file
   - this file
   - previous repository
   - previous file

3. Do not repeat the entire conversation unless necessary.

4. Do not invent repository names, owners, files, paths,
   code, GitHub statistics, profile information, or other
   GitHub information.

5. If actual GitHub data is provided above, base your answer
   on that data.

6. If the user asks for GitHub account/profile information:

   - Use the GITHUB PROFILE data above.
   - Present the available fields clearly.
   - Do not say that account information is unavailable if
     profile data is provided.
   - Do not invent missing profile fields.
   - Only show fields that actually exist in the profile data.
   - Important fields may include:
     username, name, bio, company, location, email,
     public repositories, followers, following, created date,
     profile URL, and other fields returned by GitHub.

7. If an error is provided, clearly explain the error.

8. For repository lists:
   present repositories in a clean readable format.

9. For repository structure:
   present the structure as a readable tree.

10. For file content:
    show the actual file path and content when the user
    explicitly asks to see the file.

11. For file analysis:
    explain:
    - repository
    - full file path
    - purpose
    - important logic
    - functions/classes
    - dependencies
    - potential issues
    - possible improvements

12. If the user asks a follow-up about a previous file,
    use the current state and conversation context.

13. If the user asks a follow-up about a previous repository,
    use the current repository owner and repository name.

14. If the user only asks for repository structure,
    do not unnecessarily analyze the files.

15. If the user asks for file analysis,
    do not dump the entire repository structure unless
    it is relevant.

16. If a requested filename was resolved to an actual path,
    clearly mention the resolved path.

17. If multiple files were found, do not choose one.
    Tell the user that multiple matching files were found
    and ask which one they want.

18. Keep the response concise but useful.

19. Never mention:
    - LangGraph
    - MCP
    - state
    - nodes
    - prompts
    - internal routing
    - internal implementation details

20. Respond naturally as a conversational GitHub assistant.

--------------------------------------------------
FINAL ANSWER
--------------------------------------------------
"""

    response = await llm.ainvoke(
        prompt
    )

    content = response.content

    if isinstance(
        content,
        list,
    ):

        content = "".join(
            item.get("text", "")
            for item in content
            if isinstance(
                item,
                dict,
            )
        )

    return {
        "response": content.strip()
    }


# ============================================================
# DIRECT RESPONSE NODE
# ============================================================

async def direct_response_node(
    state: AgentState,
):

    return {
        "response": state.get(
            "direct_response",
            "I couldn't find that information.",
        )
    }
