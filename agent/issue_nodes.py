from langgraph.types import interrupt

from agent.state import AgentState
from github_mcp.client import GitHubMCPClient
from github_mcp.tools import create_issue
from llm.models import get_llm


llm = get_llm()
github_client = GitHubMCPClient()


# ============================================================
# FILE ANALYSIS NODE
# ============================================================

async def file_analysis_node(
    state: AgentState,
):

    file_content = state.get("file_content") or ""
    repository_owner = state.get("repository_owner")
    repository_name = state.get("repository_name")
    file_path = state.get("file_path")

    if state.get("error"):
        return {
            "analysis_result": {
                "error": state.get("error"),
            }
        }

    if not file_content:
        return {
            "analysis_result": {
                "error": "No file content was available for analysis."
            }
        }

    prompt = f"""
You are a senior software engineer reviewing a GitHub source file.

Analyze ONLY the provided file. Do not invent code, behavior, dependencies,
issues, or repository information that is not supported by the file content.

Repository: {repository_owner}/{repository_name}
File: {file_path}

FILE CONTENT:
--------------------
{file_content}
--------------------

Return a concise but useful analysis with these sections:

1. Purpose
2. Important logic
3. Functions/classes
4. Dependencies
5. Potential issues
6. Possible improvements

For potential issues:
- Only report concrete or strongly supported problems.
- Do not call normal design choices bugs without evidence.
- If no meaningful problem is found, explicitly say so.

Return ONLY valid JSON with this structure:
{{
    "summary": "...",
    "purpose": "...",
    "important_logic": ["..."],
    "functions_classes": ["..."],
    "dependencies": ["..."],
    "potential_issues": [
        {{
            "title": "...",
            "description": "...",
            "severity": "low|medium|high|critical"
        }}
    ],
    "possible_improvements": ["..."]
}}
"""

    response = await llm.ainvoke(prompt)
    content = response.content

    if isinstance(content, list):
        content = "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict)
        )

    content = content.strip()

    if content.startswith("```"):
        content = content.replace("```json", "", 1)
        content = content.replace("```", "")
        content = content.strip()

    import json

    try:
        analysis = json.loads(content)
    except json.JSONDecodeError:
        analysis = {
            "summary": content,
            "purpose": "",
            "important_logic": [],
            "functions_classes": [],
            "dependencies": [],
            "potential_issues": [],
            "possible_improvements": [],
        }

    return {
        "analysis_result": analysis,
    }



# ============================================================
# ISSUE PROPOSAL NODE
# ============================================================

async def issue_proposal_node(
    state: AgentState,
):
    analysis = state.get("analysis_result") or {}
    user_query = state.get("user_query", "")
    owner = state.get("repository_owner")
    repo = state.get("repository_name")
    file_path = state.get("file_path") or state.get("requested_file")

    # --------------------------------------------------
    # 1. Detect conditional vs mandatory issue creation
    # --------------------------------------------------

    query_lower = user_query.lower()

    conditional_phrases = [
        "if you find a problem",
        "if there is a problem",
        "if you find an issue",
        "if there is an issue",
        "if you identify a problem",
        "if you identify an issue",
        "if you think there is a problem",
        "if you think there is an issue",
        "if necessary",
        "if needed",
        "only if",
    ]

    conditional_request = any(
        phrase in query_lower
        for phrase in conditional_phrases
    )

    force_create = not conditional_request
    issues = analysis.get("potential_issues", [])

    # --------------------------------------------------
    # 2. Conditional request: no issue if no problem found
    # --------------------------------------------------

    if conditional_request and not issues:
        return {
            "issue_proposal": {
                "should_create": False,
                "reason": (
                    "The file analysis did not identify a concrete problem. "
                    "No issue was proposed because you requested issue "
                    "creation only if a problem was found."
                ),
            }
        }

    # --------------------------------------------------
    # 3. Generate issue proposal
    # --------------------------------------------------

    prompt = f"""
Create a GitHub issue proposal from the information below.

Repository: {owner}/{repo}
File: {file_path}
User request: {user_query}

Analysis:
{analysis}

Issue creation mode: {
    "MANDATORY: the user explicitly requested issue creation."
    if force_create
    else "CONDITIONAL: create an issue only for a concrete problem."
}

Rules:
- Do not invent facts or claim an unconfirmed bug exists.
- The issue title must be specific and actionable.
- If a concrete problem exists, explain it using evidence from the analysis.
- If no concrete problem was identified and creation is mandatory,
  create a tracking/review issue explaining that the file was analyzed,
  no confirmed defect was identified, and the issue is being created
  at the user's request.
- In that case, do not describe a hypothetical problem as an actual bug.
- If creation is conditional and no concrete problem was found,
  do not create an issue.
- Include a clear reason for the proposal.

Return ONLY valid JSON:
{{
    "should_create": true,
    "title": "...",
    "body": "...",
    "reason": "..."
}}
"""

    response = await llm.ainvoke(prompt)
    content = response.content

    if isinstance(content, list):
        content = "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict)
        )

    content = content.strip()

    if content.startswith("```"):
        content = content.replace("```json", "", 1)
        content = content.replace("```", "")
        content = content.strip()

    import json

    try:
        proposal = json.loads(content)
    except json.JSONDecodeError:
        return {
            "issue_proposal": {
                "should_create": False,
                "reason": (
                    "Could not safely generate a valid GitHub issue proposal."
                ),
            }
        }

    # --------------------------------------------------
    # 4. Enforce mandatory creation
    # --------------------------------------------------

    if force_create:
        proposal["should_create"] = True

        # Fallback if the LLM omitted the title or body.
        if not proposal.get("title"):
            proposal["title"] = (
                f"Review {file_path}"
                if file_path
                else "Code review requested"
            )

        if not proposal.get("body"):
            proposal["body"] = (
                f"File reviewed: {file_path}\n\n"
                "The analysis did not identify a confirmed defect. "
                "This issue was created at the user's request to track "
                "the review. No specific bug is being asserted."
            )

        if not proposal.get("reason"):
            proposal["reason"] = (
                "Issue creation was explicitly requested by the user."
            )

    elif not proposal.get("should_create"):
        return {
            "issue_proposal": proposal,
        }

    # --------------------------------------------------
    # 5. Return proposal to the existing approval workflow
    # --------------------------------------------------

    return {
        "issue_title": proposal.get("title", "").strip(),
        "issue_body": proposal.get("body", "").strip(),
        "issue_repository_owner": owner,
        "issue_repository_name": repo,
        "issue_proposal": proposal,
    }


# ============================================================
# ISSUE APPROVAL NODE
# ============================================================

def issue_approval_node(
    state: AgentState,
):

    proposal = state.get("issue_proposal") or {}

    if proposal.get("should_create") is False:
        return {
            "issue_approved": False,
            "response": proposal.get(
                "reason",
                "No GitHub issue was created.",
            ),
        }

    decision = interrupt({
        "type": "github_issue_approval",
        "message": "A GitHub issue is ready to be created. Approve it?",
        "repository": (
            f"{state.get('issue_repository_owner')}/"
            f"{state.get('issue_repository_name')}"
        ),
        "title": state.get("issue_title", ""),
        "body": state.get("issue_body", ""),
    })

    approved = False

    if isinstance(decision, bool):
        approved = decision
    elif isinstance(decision, str):
        approved = decision.strip().lower() in {
            "yes",
            "y",
            "approve",
            "approved",
            "true",
        }
    elif isinstance(decision, dict):
        approved = bool(decision.get("approved"))

    return {
        "issue_approved": approved,
    }


# ============================================================
# ISSUE APPROVAL ROUTER
# ============================================================

def route_issue_approval(
    state: AgentState,
):

    if state.get("issue_approved") is True:
        return "create_issue"

    return "issue_response"


# ============================================================
# CREATE ISSUE NODE
# ============================================================

# ============================================================
# CREATE ISSUE NODE
# ============================================================

async def create_issue_node(
    state: AgentState,
):

    owner = state.get("issue_repository_owner")
    repo = state.get("issue_repository_name")
    title = state.get("issue_title")
    body = state.get("issue_body")

    if not owner or not repo:
        return {
            "issue_error": "Repository information is missing.",
            "response": (
                "I could not create the issue because "
                "the repository is missing."
            ),
        }

    github_client = GitHubMCPClient(
    access_token=state["github_access_token"]
    )

    session = await github_client.connect()

    try:
        result = await create_issue(
            session,
            owner=owner,
            repo=repo,
            title=title,
            body=body,
        )

        issue_number = None
        issue_url = None

        for content in getattr(result, "content", []) or []:
            text = getattr(content, "text", None)

            if not text:
                continue

            import re

            number_match = re.search(
                r'"number"\s*:\s*(\d+)',
                text,
            )

            url_match = re.search(
                r'"html_url"\s*:\s*"([^"]+)"',
                text,
            )

            if number_match:
                issue_number = int(
                    number_match.group(1)
                )

            if url_match:
                issue_url = url_match.group(1)

        # ----------------------------------------------------
        # Build final user-visible response
        # ----------------------------------------------------

        response_lines = [
            "## ✅ GitHub issue created",
            "",
            f"**Repository:** `{owner}/{repo}`",
        ]

        if issue_number:
            response_lines.append(
                f"**Issue:** `#{issue_number}`"
            )

        response_lines.extend(
            [
                "",
                f"**Title:** {title}",
                "",
                "**Issue body:**",
                "",
                body or "",
            ]
        )

        if issue_url:
            response_lines.extend(
                [
                    "",
                    f"🔗 [Open issue on GitHub]({issue_url})",
                ]
            )

        message = "\n".join(
            response_lines
        )

        return {
            "issue_number": issue_number,
            "issue_url": issue_url,
            "response": message,
        }

    except Exception as exc:

        return {
            "issue_error": str(exc),
            "response": (
                f"I could not create the GitHub issue: {exc}"
            ),
        }

    finally:
        await github_client.close()


# ============================================================
# ISSUE RESPONSE NODE
# ============================================================

async def issue_response_node(
    state: AgentState,
):

    if state.get("response"):
        return {
            "response": state.get("response"),
        }

    return {
        "response": "The GitHub issue was not created.",
    }
