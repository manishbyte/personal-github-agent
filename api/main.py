import os

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from api.auth.routes import router as auth_router
from fastapi import Depends, HTTPException
from sqlalchemy import select

from api.dependencies import get_current_user
from database.models import GitHubToken, User
from github_mcp.client import GitHubMCPClient
from database.connection import get_db
from api.chat import router as chat_router

from api.conversations import (
    router as conversations_router
)
load_dotenv()


SESSION_SECRET = os.getenv("SESSION_SECRET")


if not SESSION_SECRET:
    raise RuntimeError(
        "SESSION_SECRET is not configured."
    )


app = FastAPI(
    title="Personal GitHub Agent API",
    version="1.0.0",
)


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
)


app.include_router(
    auth_router
)

app.include_router(
    chat_router
)

app.include_router(
    conversations_router
)


@app.get("/health")
async def health_check():

    return {
        "status": "ok",
    }

@app.get("/api/github/test")
async def github_mcp_test(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(
        select(GitHubToken).where(
            GitHubToken.user_id == current_user.id
        )
    )

    github_token = result.scalar_one_or_none()

    if not github_token:
        raise HTTPException(
            status_code=401,
            detail="GitHub token not found.",
        )

    client = GitHubMCPClient(
        access_token=github_token.access_token
    )

    try:
        session = await client.connect()

        mcp_result = await session.call_tool(
            "get_me",
            {},
        )

        return {
            "status": "success",
            "database_user": current_user.github_username,
            "mcp_result": mcp_result.model_dump()
            if hasattr(mcp_result, "model_dump")
            else str(mcp_result),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"GitHub MCP test failed: {str(exc)}",
        )

    finally:
        await client.close()