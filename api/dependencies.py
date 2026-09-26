from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from database.connection import get_db
from database.models import User
from dotenv import load_dotenv

import os


load_dotenv()


SESSION_SECRET = os.getenv(
    "SESSION_SECRET"
)


if not SESSION_SECRET:
    raise RuntimeError(
        "SESSION_SECRET is not configured."
    )


streamlit_serializer = URLSafeTimedSerializer(
    SESSION_SECRET
)


STREAMLIT_TOKEN_MAX_AGE = 3600


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:

    # --------------------------------------------------------
    # 1. Existing FastAPI session authentication
    # --------------------------------------------------------

    user_id = request.session.get(
        "user_id"
    )

    if user_id:

        result = await db.execute(
            select(User).where(
                User.id == user_id
            )
        )

        user = result.scalar_one_or_none()

        if not user:

            request.session.pop(
                "user_id",
                None
            )

            raise HTTPException(
                status_code=401,
                detail="Authenticated user no longer exists.",
            )

        return user

    # --------------------------------------------------------
    # 2. Streamlit authentication
    # --------------------------------------------------------

    authorization = request.headers.get(
        "Authorization"
    )

    if not authorization:

        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
        )

    if not authorization.startswith(
        "Bearer "
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid authentication header.",
        )

    token = authorization[
        len("Bearer "):
    ]

    try:

        data = streamlit_serializer.loads(
            token,
            max_age=STREAMLIT_TOKEN_MAX_AGE,
        )

    except SignatureExpired:

        raise HTTPException(
            status_code=401,
            detail="Authentication token expired.",
        )

    except BadSignature:

        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token.",
        )

    user_id = data.get(
        "user_id"
    )

    if not user_id:

        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token.",
        )

    result = await db.execute(
        select(User).where(
            User.id == user_id
        )
    )

    user = result.scalar_one_or_none()

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Authenticated user no longer exists.",
        )

    return user


__all__ = [
    "get_db",
    "get_current_user",
]