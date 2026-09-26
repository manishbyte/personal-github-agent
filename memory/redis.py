import json
import os
from typing import Any

import redis.asyncio as redis
from dotenv import load_dotenv


load_dotenv()


class RedisMemory:

    def __init__(self):
        self.host = os.getenv(
            "REDIS_HOST",
            "localhost",
        )

        self.port = int(
            os.getenv(
                "REDIS_PORT",
                "6379",
            )
        )

        self.db = int(
            os.getenv(
                "REDIS_DB",
                "0",
            )
        )

        self.ttl = int(
            os.getenv(
                "REDIS_TTL",
                "86400",
            )
        )

        self.client = None

    def _get_client(self):
        if self.client is None:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True,
            )

        return self.client

    async def ping(self):
        client = self._get_client()
        return await client.ping()

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ):
        client = self._get_client()

        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        await client.set(
            key,
            value,
            ex=ttl or self.ttl,
        )

    async def get(
        self,
        key: str,
    ) -> Any:

        client = self._get_client()

        value = await client.get(key)

        if value is None:
            return None

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    async def delete(
        self,
        key: str,
    ):
        client = self._get_client()

        await client.delete(key)

    def key(
        self,
        session_id: str,
        field: str,
    ) -> str:
        return f"github:{session_id}:{field}"

    async def set_memory(
        self,
        session_id: str,
        field: str,
        value: Any,
    ):
        await self.set(
            self.key(
                session_id,
                field,
            ),
            value,
        )

    async def get_memory(
        self,
        session_id: str,
        field: str,
    ):
        return await self.get(
            self.key(
                session_id,
                field,
            )
        )

    async def delete_memory(
        self,
        session_id: str,
        field: str,
    ):
        await self.delete(
            self.key(
                session_id,
                field,
            )
        )

    async def close(self):
        if self.client is not None:
            await self.client.aclose()
            self.client = None