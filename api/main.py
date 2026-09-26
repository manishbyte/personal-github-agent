import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from api.auth.routes import router as auth_router
from api.dependencies import get_current_user
from api.chat import router as chat_router
from api.conversations import router as conversations_router

from database.connection import Base, engine, get_db
from database.models import GitHubToken, User

from github_mcp.client import GitHubMCPClient

# Load environment variables
load_dotenv()


SESSION_SECRET = os.getenv("SESSION_SECRET")

if not SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET is not configured.")


# Register all SQLAlchemy models before creating tables
import database.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables when the application starts."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Dispose of database connections during shutdown
    await engine.dispose()


# Initialize FastAPI
app = FastAPI(
    title="Personal GitHub Agent API",
    version="1.0.0",
    lifespan=lifespan,
)


# Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
)


# Register routers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(conversations_router)


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
            "mcp_result": (
                mcp_result.model_dump()
                if hasattr(mcp_result, "model_dump")
                else str(mcp_result)
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"GitHub MCP test failed: {str(exc)}",
        ) from exc

    finally:
        await client.close()