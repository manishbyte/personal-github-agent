
from uuid import uuid4
from typing import Any

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from agent.graph import build_graph
from database.connection import get_db
from database.models import (
    User,
    GitHubToken,
    Conversation,
    ConversationMessage,
)


router = APIRouter(
    prefix="/api/chat",
    tags=["chat"],
)


class ChatRequest(BaseModel):
    message: str | None = Field(
        default=None,
        min_length=1,
        max_length=10000,
    )
    session_id: str | None = None
    approval: bool | None = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    requires_approval: bool = False
    approval_request: dict[str, Any] | None = None


graph = build_graph()


@router.post(
    "",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # --------------------------------------------------
    # 1. Validate request
    # --------------------------------------------------

    is_resuming = request.approval is not None

    if not is_resuming and not request.message:
        raise HTTPException(
            status_code=422,
            detail="A message is required.",
        )

    if is_resuming and not request.session_id:
        raise HTTPException(
            status_code=400,
            detail="session_id is required to resume approval.",
        )

    session_id = request.session_id or str(uuid4())

    # --------------------------------------------------
    # 2. Find the user's conversation
    # --------------------------------------------------

    result = await db.execute(
        select(Conversation).where(
            Conversation.session_id == session_id,
            Conversation.user_id == current_user.id,
        )
    )

    conversation = result.scalar_one_or_none()

    if conversation is None:
        if is_resuming:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        conversation = Conversation(
            user_id=current_user.id,
            session_id=session_id,
            title=request.message[:500],
        )

        db.add(conversation)
        await db.flush()

    # --------------------------------------------------
    # 3. Prepare initial request OR resume approval
    # --------------------------------------------------

    config = {
        "configurable": {
            "thread_id": session_id,
        }
    }

    if is_resuming:
        # Resume the existing paused LangGraph execution.
        # Do not start a new graph or add another user message.
        result = await graph.ainvoke(
            Command(resume=request.approval),
            config=config,
        )

    else:
        # ----------------------------------------------
        # 3.1 Load conversation history from PostgreSQL
        # ----------------------------------------------

        message_result = await db.execute(
            select(ConversationMessage)
            .where(
                ConversationMessage.conversation_id
                == conversation.id
            )
            .order_by(
                ConversationMessage.id.asc()
            )
        )

        previous_messages = message_result.scalars().all()

        conversation_messages = []

        for message in previous_messages:
            if message.role == "user":
                conversation_messages.append(
                    HumanMessage(content=message.content)
                )

            elif message.role == "assistant":
                conversation_messages.append(
                    AIMessage(content=message.content)
                )

        conversation_messages.append(
            HumanMessage(content=request.message)
        )

        # ----------------------------------------------
        # 3.2 Save the user's message
        # ----------------------------------------------

        user_message = ConversationMessage(
            conversation_id=conversation.id,
            role="user",
            content=request.message,
        )

        db.add(user_message)
        await db.flush()

        # ----------------------------------------------
        # 3.3 Get the authenticated user's GitHub token
        # ----------------------------------------------

        token_result = await db.execute(
            select(GitHubToken).where(
                GitHubToken.user_id == current_user.id
            )
        )

        github_token = token_result.scalar_one_or_none()

        if github_token is None:
            raise HTTPException(
                status_code=401,
                detail="GitHub account is not connected.",
            )

        # ----------------------------------------------
        # 3.4 Start LangGraph
        # ----------------------------------------------

        initial_state = {
            "user_query": request.message,
            "messages": conversation_messages,
            "session_id": session_id,
            "github_username": current_user.github_username,
            "github_access_token": github_token.access_token,
        }

        result = await graph.ainvoke(
            initial_state,
            config=config,
        )

    # --------------------------------------------------
    # 4. Handle LangGraph approval interrupt
    # --------------------------------------------------

    interrupts = result.get("__interrupt__", [])

    if interrupts:
        interrupt_data = getattr(
            interrupts[0],
            "value",
            {},
        )

        # Persist the conversation and user message, but do
        # not save a fake assistant response while paused.
        await db.commit()

        return ChatResponse(
            session_id=session_id,
            response=(
                "Please review the proposed GitHub issue "
                "and approve or reject it."
            ),
            requires_approval=True,
            approval_request=interrupt_data,
        )

    # --------------------------------------------------
    # 5. Extract final response
    # --------------------------------------------------

    response = result.get("response")

    if not response:
        response = result.get("direct_response")

    if not response:
        response = (
            "The workflow finished without returning a response. "
            "Check the LangGraph state and node execution."
        )

    # --------------------------------------------------
    # 6. Save the final assistant response
    # --------------------------------------------------

    assistant_message = ConversationMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=response,
    )

    db.add(assistant_message)

    # --------------------------------------------------
    # 7. Commit and return
    # --------------------------------------------------

    await db.commit()

    return ChatResponse(
        session_id=session_id,
        response=response,
        requires_approval=False,
        approval_request=None,
    )

