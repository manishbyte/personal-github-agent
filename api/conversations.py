from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy import (
    select,
)

from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    get_current_user,
)

from database.connection import (
    get_db,
)

from database.models import (
    User,
    Conversation,
    ConversationMessage,
)


router = APIRouter(
    prefix="/api/conversations",
    tags=["Conversations"],
)


# ============================================================
# LIST CONVERSATIONS
# ============================================================

@router.get("")
async def get_conversations(
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
):

    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id
            == current_user.id
        )
        .order_by(
            Conversation.updated_at.desc()
        )
    )

    conversations = result.scalars().all()

    return [
        {
            "id": conversation.id,
            "session_id": conversation.session_id,
            "title": conversation.title,
            "created_at": (
                conversation.created_at.isoformat()
                if conversation.created_at
                else None
            ),
            "updated_at": (
                conversation.updated_at.isoformat()
                if conversation.updated_at
                else None
            ),
        }
        for conversation in conversations
    ]


# ============================================================
# GET CONVERSATION MESSAGES
# ============================================================

@router.get(
    "/{session_id}"
)
async def get_conversation(
    session_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
):

    result = await db.execute(
        select(Conversation).where(
            Conversation.session_id
            == session_id,
            Conversation.user_id
            == current_user.id,
        )
    )

    conversation = (
        result.scalar_one_or_none()
    )

    if not conversation:

        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    result = await db.execute(
        select(
            ConversationMessage
        )
        .where(
            ConversationMessage.conversation_id
            == conversation.id
        )
        .order_by(
            ConversationMessage.created_at.asc()
        )
    )

    messages = result.scalars().all()

    return {
        "session_id": conversation.session_id,
        "title": conversation.title,
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "created_at": (
                    message.created_at.isoformat()
                    if message.created_at
                    else None
                ),
            }
            for message in messages
        ],
    }


# ============================================================
# USER PROFILE
# ============================================================

@router.get(
    "/user/me"
)
async def get_user_profile(
    current_user: User = Depends(
        get_current_user
    ),
):

    return {
        "id": current_user.id,
        "github_id": current_user.github_id,
        "github_username": (
            current_user.github_username
        ),
        "github_name": (
            current_user.github_name
        ),
        "github_email": (
            current_user.github_email
        ),
        "github_avatar_url": (
            current_user.github_avatar_url
        ),
    }