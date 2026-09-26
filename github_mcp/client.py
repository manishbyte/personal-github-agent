import os
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


# Load .env from project root
BASE_DIR = Path(__file__).resolve().parents[1]

load_dotenv(BASE_DIR / ".env")


GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"


class GitHubMCPClient:

    def __init__(
        self,
        access_token: str | None = None,
    ):

        self.token = (
            access_token
            if access_token
            else os.getenv("GITHUB_TOKEN")
        )

    async def connect(self):

        if not self.token:

            raise ValueError(
                "GITHUB_TOKEN is not set. "
                "Check your .env file."
            )

        self.client = streamablehttp_client(
            GITHUB_MCP_URL,
            headers={
                "Authorization": f"Bearer {self.token}",
            },
        )

        self.read, self.write, self.session_id = (
            await self.client.__aenter__()
        )

        self.session = ClientSession(
            self.read,
            self.write,
        )

        await self.session.__aenter__()

        await self.session.initialize()

        return self.session

    async def close(self):

        if hasattr(self, "session"):

            await self.session.__aexit__(
                None,
                None,
                None,
            )

        if hasattr(self, "client"):

            await self.client.__aexit__(
                None,
                None,
                None,
            )