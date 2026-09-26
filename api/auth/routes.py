import secrets
import os

from datetime import datetime, timedelta

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from fastapi.responses import RedirectResponse

from sqlalchemy import select

from itsdangerous import URLSafeTimedSerializer

from api.auth.github_oauth import (
    exchange_code_for_token,
    get_github_authorization_url,
    get_github_emails,
    get_github_user,
)

from api.dependencies import get_current_user

from database.connection import AsyncSessionLocal

from database.models import (
    GitHubToken,
    User,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


SESSION_SECRET = os.getenv(
    "SESSION_SECRET"
)

if not SESSION_SECRET:
    raise RuntimeError(
        "SESSION_SECRET is not configured."
    )


STREAMLIT_URL = os.getenv(
    "STREAMLIT_URL",
    "http://localhost:8501",
)


streamlit_serializer = URLSafeTimedSerializer(
    SESSION_SECRET
)


@router.get("/github")
async def github_login(
    request: Request,
):

    state = secrets.token_urlsafe(32)

    request.session["github_oauth_state"] = state

    authorization_url = get_github_authorization_url(
        state
    )

    return RedirectResponse(
        authorization_url
    )


@router.get("/github/callback")
async def github_callback(
    request: Request,
):

    code = request.query_params.get(
        "code"
    )

    state = request.query_params.get(
        "state"
    )

    error = request.query_params.get(
        "error"
    )

    if error:
        raise HTTPException(
            status_code=400,
            detail=f"GitHub OAuth failed: {error}",
        )

    if not code:
        raise HTTPException(
            status_code=400,
            detail="GitHub authorization code is missing.",
        )

    if not state:
        raise HTTPException(
            status_code=400,
            detail="GitHub OAuth state is missing.",
        )

    stored_state = request.session.get(
        "github_oauth_state"
    )

    if not stored_state:
        raise HTTPException(
            status_code=400,
            detail="GitHub OAuth session state is missing.",
        )

    if not secrets.compare_digest(
        stored_state,
        state,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub OAuth state.",
        )

    request.session.pop(
        "github_oauth_state",
        None,
    )

    token_data = await exchange_code_for_token(
        code
    )

    access_token = token_data.get(
        "access_token"
    )

    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="GitHub access token was not returned.",
        )

    github_user = await get_github_user(
        access_token
    )

    github_emails = await get_github_emails(
        access_token
    )

    github_email = github_user.get(
        "email"
    )

    if not github_email:

        for email_data in github_emails:

            if email_data.get("primary"):
                github_email = email_data.get(
                    "email"
                )
                break

    github_id = github_user.get(
        "id"
    )

    github_username = github_user.get(
        "login"
    )

    if not github_id or not github_username:
        raise HTTPException(
            status_code=400,
            detail="GitHub user information is incomplete.",
        )

    expires_at = None

    if token_data.get("expires_in"):

        expires_at = (
            datetime.utcnow()
            + timedelta(
                seconds=int(
                    token_data["expires_in"]
                )
            )
        )

    refresh_token_expires_at = None

    if token_data.get(
        "refresh_token_expires_in"
    ):

        refresh_token_expires_at = (
            datetime.utcnow()
            + timedelta(
                seconds=int(
                    token_data[
                        "refresh_token_expires_in"
                    ]
                )
            )
        )

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(User).where(
                User.github_id == github_id
            )
        )

        user = result.scalar_one_or_none()

        if user:

            user.github_username = (
                github_username
            )

            user.github_name = (
                github_user.get("name")
            )

            user.github_email = (
                github_email
            )

            user.github_avatar_url = (
                github_user.get("avatar_url")
            )

        else:

            user = User(
                github_id=github_id,
                github_username=github_username,
                github_name=github_user.get(
                    "name"
                ),
                github_email=github_email,
                github_avatar_url=github_user.get(
                    "avatar_url"
                ),
            )

            db.add(user)

            await db.flush()

        result = await db.execute(
            select(GitHubToken).where(
                GitHubToken.user_id == user.id
            )
        )

        github_token = (
            result.scalar_one_or_none()
        )

        if github_token:

            github_token.access_token = (
                access_token
            )

            github_token.refresh_token = (
                token_data.get(
                    "refresh_token"
                )
            )

            github_token.expires_at = (
                expires_at
            )

            github_token.refresh_token_expires_at = (
                refresh_token_expires_at
            )

        else:

            github_token = GitHubToken(
                user_id=user.id,
                access_token=access_token,
                refresh_token=token_data.get(
                    "refresh_token"
                ),
                expires_at=expires_at,
                refresh_token_expires_at=(
                    refresh_token_expires_at
                ),
            )

            db.add(github_token)

        await db.commit()

        await db.refresh(user)

        request.session["user_id"] = user.id

        streamlit_token = streamlit_serializer.dumps(
            {
                "user_id": user.id,
            }
        )

        redirect_url = (
            f"{STREAMLIT_URL}"
            f"?auth_token={streamlit_token}"
        )

        return RedirectResponse(
            redirect_url
        )


@router.get("/me")
async def get_me(
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
        "github_name": current_user.github_name,
        "github_email": current_user.github_email,
        "github_avatar_url": (
            current_user.github_avatar_url
        ),
    }
