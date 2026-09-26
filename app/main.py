import asyncio

import streamlit as st
from langgraph.types import Command

from agent.graph import build_graph


st.set_page_config(
    page_title="Personal GitHub Agent",
    page_icon="🐙",
    layout="wide",
)


st.title("🐙 Personal GitHub Agent")

st.caption(
    "Ask about your GitHub profile, repositories, files, "
    "and continue the conversation naturally."
)


# ============================================================
# SESSION
# ============================================================

if "graph" not in st.session_state:
    st.session_state.graph = build_graph()


if "messages" not in st.session_state:
    st.session_state.messages = []


if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = None


# ============================================================
# REDIS SESSION ID
# ============================================================

if "session_id" not in st.session_state:
    st.session_state.session_id = "github-chat"


session_id = st.session_state.session_id


config = {
    "configurable": {
        "thread_id": session_id,
    }
}


# ============================================================
# DISPLAY CHAT HISTORY
# ============================================================

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):
        st.markdown(
            message["content"]
        )


# ============================================================
# INTERRUPT HANDLER
# ============================================================

def get_interrupt_data(result):

    interrupts = result.get(
        "__interrupt__"
    )

    if not interrupts:
        return None

    interrupt = interrupts[0]

    if hasattr(
        interrupt,
        "value",
    ):
        return interrupt.value

    if isinstance(
        interrupt,
        dict,
    ):
        return interrupt

    return None


# ============================================================
# HANDLE GRAPH RESULT
# ============================================================

def handle_graph_result(result):

    approval_data = get_interrupt_data(
        result
    )

    if approval_data:

        st.session_state.pending_approval = (
            approval_data
        )

        return None

    return result.get(
        "response",
        "Something went wrong.",
    )


# ============================================================
# PENDING GITHUB ISSUE APPROVAL
# ============================================================

pending_approval = (
    st.session_state.pending_approval
)


if pending_approval:

    st.divider()

    st.subheader(
        "🐙 GitHub Issue Approval"
    )

    repository = pending_approval.get(
        "repository",
        "Unknown repository",
    )

    title = pending_approval.get(
        "title",
        "",
    )

    body = pending_approval.get(
        "body",
        "",
    )

    st.markdown(
        f"**Repository:** `{repository}`"
    )

    st.markdown(
        f"**Title:** {title}"
    )

    st.markdown(
        "**Issue body:**"
    )

    st.code(
        body,
        language="markdown",
    )

    col1, col2 = st.columns(2)

    # --------------------------------------------------------
    # APPROVE
    # --------------------------------------------------------

    with col1:

        if st.button(
            "Approve & Create Issue",
            type="primary",
            use_container_width=True,
        ):

            with st.spinner(
                "Creating GitHub issue..."
            ):

                result = asyncio.run(
                    st.session_state.graph.ainvoke(
                        Command(
                            resume={
                                "approved": True,
                            }
                        ),
                        config=config,
                    )
                )

            response = result.get(
                "response",
                "Something went wrong.",
            )

            st.session_state.pending_approval = None

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": response,
                }
            )

            st.rerun()

    # --------------------------------------------------------
    # REJECT
    # --------------------------------------------------------

    with col2:

        if st.button(
            "Reject",
            use_container_width=True,
        ):

            with st.spinner(
                "Cancelling issue creation..."
            ):

                result = asyncio.run(
                    st.session_state.graph.ainvoke(
                        Command(
                            resume={
                                "approved": False,
                            }
                        ),
                        config=config,
                    )
                )

            response = result.get(
                "response",
                "The GitHub issue was not created.",
            )

            st.session_state.pending_approval = None

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": response,
                }
            )

            st.rerun()


# ============================================================
# USER INPUT
# ============================================================

user_query = st.chat_input(
    "Ask something about your GitHub..."
)


if user_query:

    # --------------------------------------------------------
    # Display user message
    # --------------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_query,
        }
    )

    with st.chat_message("user"):
        st.markdown(user_query)

    # --------------------------------------------------------
    # Agent
    # --------------------------------------------------------

    with st.chat_message("assistant"):

        with st.spinner("Thinking..."):

            result = asyncio.run(
                st.session_state.graph.ainvoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": user_query,
                            }
                        ],
                        "user_query": user_query,
                        "session_id": session_id,
                    },
                    config=config,
                )
            )

            response = handle_graph_result(
                result
            )

            if response:

                st.markdown(
                    response
                )

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": response,
                    }
                )

            else:

                st.rerun()