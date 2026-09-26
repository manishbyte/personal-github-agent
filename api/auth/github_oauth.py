import os

import httpx
from dotenv import load_dotenv


load_dotenv()


GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI")

import logging

logger = logging.getLogger(__name__)


if not GITHUB_CLIENT_ID:
    raise RuntimeError(
        "GITHUB_CLIENT_ID is not configured."
    )

if not GITHUB_CLIENT_SECRET:
    raise RuntimeError(
        "GITHUB_CLIENT_SECRET is not configured."
    )

if not GITHUB_REDIRECT_URI:
    raise RuntimeError(
        "GITHUB_REDIRECT_URI is not configured."
    )


GITHUB_AUTHORIZE_URL = (
    "https://github.com/login/oauth/authorize"
)

GITHUB_ACCESS_TOKEN_URL = (
    "https://github.com/login/oauth/access_token"
)

GITHUB_USER_URL = (
    "https://api.github.com/user"
)

GITHUB_EMAILS_URL = (
    "https://api.github.com/user/emails"
)


def get_github_authorization_url(
    state: str,
) -> str:

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "read:user user:email repo",
        "state": state,
    }

    query = httpx.QueryParams(params)

    return f"{GITHUB_AUTHORIZE_URL}?{query}"


async def exchange_code_for_token(code: str) -> dict:
    data = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": GITHUB_REDIRECT_URI,
    }

    headers = {
        "Accept": "application/json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            GITHUB_ACCESS_TOKEN_URL,
            data=data,
            headers=headers,
        )

        response.raise_for_status()
        token_data = response.json()

        # Log the OAuth error without exposing credentials or tokens.
        if not token_data.get("access_token"):
            logger.error(
                "GitHub OAuth token exchange failed: error=%s, description=%s",
                token_data.get("error", "unknown_error"),
                token_data.get(
                    "error_description",
                    "No error description provided",
                ),
            )

        return token_data


async def get_github_user(
    access_token: str,
) -> dict:

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:

        response = await client.get(
            GITHUB_USER_URL,
            headers=headers,
        )

        response.raise_for_status()

        return response.json()


async def get_github_emails(
    access_token: str,
) -> list:

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:

        response = await client.get(
            GITHUB_EMAILS_URL,
            headers=headers,
        )

        response.raise_for_status()

        return response.json()