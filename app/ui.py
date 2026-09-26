import os
from uuid import uuid4

import requests
import streamlit as st

from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://localhost:8000",
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Personal GitHub Agent",
    page_icon="🐙",
    layout="wide",
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    .login-container {
        max-width: 600px;
        margin: 100px auto;
        text-align: center;
    }

    .login-title {
        font-size: 42px;
        font-weight: 700;
        margin-bottom: 10px;
    }

    .login-subtitle {
        font-size: 18px;
        color: #888;
        margin-bottom: 35px;
    }

    .conversation-title {
        font-size: 14px;
        color: #888;
        margin-top: 15px;
        margin-bottom: 5px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

if "auth_token" not in st.session_state:
    st.session_state.auth_token = None

if "user" not in st.session_state:
    st.session_state.user = None

if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversations" not in st.session_state:
    st.session_state.conversations = []

if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = None

if "initialized" not in st.session_state:
    st.session_state.initialized = False


# ============================================================
# API HELPERS
# ============================================================

def api_headers():

    token = st.session_state.auth_token

    if not token:
        return {}

    return {
        "Authorization": f"Bearer {token}"
    }


def api_get(endpoint):

    response = requests.get(
        f"{API_BASE_URL}{endpoint}",
        headers=api_headers(),
        timeout=30,
    )

    return response


def api_post(
    endpoint,
    payload=None,
):

    response = requests.post(
        f"{API_BASE_URL}{endpoint}",
        headers=api_headers(),
        json=payload,
        timeout=120,
    )

    return response


# ============================================================
# AUTH TOKEN FROM URL
# ============================================================

query_params = st.query_params

auth_token = query_params.get(
    "auth_token"
)


if auth_token:

    st.session_state.auth_token = (
        auth_token
    )

    # Remove token from browser URL
    st.query_params.clear()

    st.rerun()


# ============================================================
# LOAD USER
# ============================================================

def load_user():

    response = api_get(
        "/api/auth/me"
    )

    if response.status_code == 200:

        return response.json()

    return None


# ============================================================
# LOAD CONVERSATIONS
# ============================================================

def load_conversations():

    response = api_get(
        "/api/conversations"
    )

    if response.status_code != 200:

        return []

    return response.json()


# ============================================================
# LOAD MESSAGES
# ============================================================

def load_messages(
    session_id
):

    response = api_get(
        f"/api/conversations/{session_id}"
    )

    if response.status_code != 200:

        return []

    data = response.json()

    return data.get(
        "messages",
        []
    )


# ============================================================
# CREATE NEW CHAT
# ============================================================

def create_new_chat():

    st.session_state.session_id = (
        str(uuid4())
    )

    st.session_state.messages = []
    st.session_state.pending_approval = None

    st.rerun()


# ============================================================
# LOGOUT
# ============================================================

def logout():

    st.session_state.auth_token = None
    st.session_state.user = None
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.conversations = []
    st.session_state.pending_approval = None
    st.session_state.initialized = False

    st.rerun()


# ============================================================
# LOGIN PAGE
# ============================================================

if not st.session_state.auth_token:

    # Center the login content
    _, center, _ = st.columns([1, 2, 1])

    with center:

        # Add spacing above the login content
        st.markdown(
            "<br><br><br>",
            unsafe_allow_html=True,
        )

        # Login title
        st.markdown(
            "<h1 style='text-align: center;'>"
            "🐙 Personal GitHub Agent"
            "</h1>",
            unsafe_allow_html=True,
        )

        # Login subtitle
        st.markdown(
            """
            <p style="
                text-align: center;
                color: #888888;
                font-size: 17px;
                margin-bottom: 30px;
            ">
                Your AI assistant for GitHub repositories,
                files, issues and code analysis.
            </p>
            """,
            unsafe_allow_html=True,
        )

        # GitHub login button
        st.link_button(
            "🐙 Login with GitHub",
            f"{API_BASE_URL}/api/auth/github",
            use_container_width=True,
        )

    st.stop()

# ============================================================
# VERIFY AUTHENTICATION
# ============================================================

if st.session_state.user is None:

    user = load_user()

    if user is None:

        st.session_state.auth_token = None

        st.error(
            "Your authentication session has expired. "
            "Please login again."
        )

        st.stop()

    st.session_state.user = user


# ============================================================
# INITIAL DATA
# ============================================================

if not st.session_state.initialized:

    st.session_state.conversations = (
        load_conversations()
    )

    st.session_state.initialized = True


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title(
        "🐙 GitHub Agent"
    )

    user = st.session_state.user

    if user.get(
        "github_avatar_url"
    ):

        st.image(
            user[
                "github_avatar_url"
            ],
            width=70,
        )

    st.write(
        f"**{user.get('github_name') or user.get('github_username')}**"
    )

    st.caption(
        f"@{user.get('github_username')}"
    )

    st.divider()

    if st.button(
        "＋ New Chat",
        use_container_width=True,
    ):

        create_new_chat()

    st.divider()

    st.subheader(
        "Conversations"
    )

    conversations = (
        st.session_state.conversations
    )

    if not conversations:

        st.caption(
            "No conversations yet."
        )

    else:

        for conversation in conversations:

            title = (
                conversation.get(
                    "title"
                )
                or "New conversation"
            )

            if len(title) > 35:

                title = (
                    title[:35]
                    + "..."
                )

            is_active = (
                conversation.get(
                    "session_id"
                )
                == st.session_state.session_id
            )

            button_label = (
                f"● {title}"
                if is_active
                else title
            )

            if st.button(
                button_label,
                key=(
                    "conversation_"
                    + conversation[
                        "session_id"
                    ]
                ),
                use_container_width=True,
            ):

                session_id = (
                    conversation[
                        "session_id"
                    ]
                )

                st.session_state.session_id = (
                    session_id
                )

                st.session_state.messages = (
                    load_messages(
                        session_id
                    )
                )
                st.session_state.pending_approval = None

                st.rerun()

    st.divider()

    if st.button(
        "Logout",
        use_container_width=True,
    ):

        logout()


# ============================================================
# ISSUE APPROVAL / REJECTION
# ============================================================

def submit_issue_approval(approved: bool):
    pending = st.session_state.pending_approval

    if not pending:
        st.warning("There is no pending issue approval.")
        return

    session_id = pending.get("session_id")

    if not session_id:
        st.error("The approval request has no session ID.")
        return

    response = api_post(
        "/api/chat",
        {
            "session_id": session_id,
            "approval": approved,
        },
    )

    if response.status_code != 200:
        st.error(
            f"API error {response.status_code}: "
            f"{response.text}"
        )
        return

    data = response.json()

    st.session_state.session_id = data.get(
        "session_id",
        session_id,
    )

    if data.get("requires_approval"):
        st.session_state.pending_approval = {
            "session_id": st.session_state.session_id,
            "request": data.get("approval_request") or {},
        }
    else:
        st.session_state.pending_approval = None

    st.session_state.messages = load_messages(
        st.session_state.session_id
    )
    st.session_state.conversations = load_conversations()

    st.rerun()


# ============================================================
# MAIN HEADER
# ============================================================

st.title(
    "Personal GitHub Agent"
)

st.caption(
    "Ask me about your GitHub repositories, "
    "files, issues and code."
)


# ============================================================
# INITIAL CHAT
# ============================================================

if not st.session_state.session_id:

    create_new_chat()


# ============================================================
# DISPLAY MESSAGES
# ============================================================

for message in st.session_state.messages:

    role = message.get(
        "role",
        "assistant",
    )

    content = message.get(
        "content",
        "",
    )

    if role not in {
        "user",
        "assistant",
    }:

        continue

    with st.chat_message(
        role
    ):

        st.markdown(
            content
        )


# ============================================================
# PENDING ISSUE APPROVAL
# ============================================================

pending = st.session_state.pending_approval

if (
    pending
    and pending.get("session_id")
    == st.session_state.session_id
):
    approval = pending.get("request") or {}

    with st.chat_message("assistant"):

        st.warning(
            approval.get(
                "message",
                "Approval is required before creating the issue.",
            )
        )

        st.write(
            f"**Repository:** "
            f"{approval.get('repository', 'Unknown')}"
        )

        st.write(
            f"**Title:** "
            f"{approval.get('title', 'Untitled issue')}"
        )

        st.markdown(
            approval.get("body", "")
        )

        col1, col2 = st.columns(2)

        with col1:
            st.button(
                "Approve and create issue",
                key=f"approve_{st.session_state.session_id}",
                use_container_width=True,
                type="primary",
                on_click=submit_issue_approval,
                args=(True,),
            )

        with col2:
            st.button(
                "Reject",
                key=f"reject_{st.session_state.session_id}",
                use_container_width=True,
                on_click=submit_issue_approval,
                args=(False,),
            )


# ============================================================
# CHAT INPUT
# ============================================================

if st.session_state.pending_approval:
    st.info(
        "Please approve or reject the proposed issue above "
        "before sending another message in this conversation."
    )
    st.stop()

user_message = st.chat_input(
    "Ask your GitHub agent..."
)


if user_message:

    # --------------------------------------------------------
    # Display user message immediately
    # --------------------------------------------------------

    with st.chat_message(
        "user"
    ):

        st.markdown(
            user_message
        )

    # --------------------------------------------------------
    # Call FastAPI chat endpoint
    # --------------------------------------------------------

    with st.chat_message(
        "assistant"
    ):

        with st.spinner(
            "Thinking..."
        ):

            response = api_post(
                "/api/chat",
                {
                    "message": user_message,
                    "session_id": (
                        st.session_state.session_id
                    ),
                },
            )

            if response.status_code == 200:

                data = response.json()

                st.session_state.session_id = (
                    data.get(
                        "session_id",
                        st.session_state.session_id,
                    )
                )

                if data.get("requires_approval"):
                    st.session_state.pending_approval = {
                        "session_id": st.session_state.session_id,
                        "request": data.get("approval_request") or {},
                    }

                    st.info(
                        "The file analysis is complete. "
                        "Review the proposed GitHub issue below."
                    )
                else:
                    st.session_state.pending_approval = None

                    assistant_response = (
                        data.get(
                            "response",
                            "No response returned.",
                        )
                    )

                    st.markdown(
                        assistant_response
                    )

            elif response.status_code == 401:

                st.session_state.auth_token = None

                st.error(
                    "Authentication expired. "
                    "Please login again."
                )

                st.stop()

            else:

                st.error(
                    f"API error "
                    f"{response.status_code}: "
                    f"{response.text}"
                )

    # --------------------------------------------------------
    # Refresh conversation list
    # --------------------------------------------------------

    st.session_state.conversations = (
        load_conversations()
    )

    # --------------------------------------------------------
    # Reload messages from PostgreSQL
    # --------------------------------------------------------

    st.session_state.messages = (
        load_messages(
            st.session_state.session_id
        )
    )

    st.rerun()