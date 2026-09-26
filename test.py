import asyncio

from agent.memory_resolver import resolve_memory
from memory.redis import RedisMemory


async def main():

    memory = RedisMemory()

    session_id = "github-chat"

    # --------------------------------------------------------
    # Prepare test memory
    # --------------------------------------------------------

    await memory.set_memory(
        session_id,
        "github_username",
        "manishbyte",
    )

    await memory.set_memory(
        session_id,
        "profile",
        {
            "login": "manishbyte",
            "name": "Manish",
        },
    )

    await memory.set_memory(
        session_id,
        "current_repository_owner",
        "openai",
    )

    await memory.set_memory(
        session_id,
        "current_repository_name",
        "openai-python",
    )

    await memory.set_memory(
        session_id,
        "current_file_path",
        "_client.py",
    )

    # --------------------------------------------------------
    # Test username
    # --------------------------------------------------------

    result = await resolve_memory(
        session_id,
        "what is my username",
    )

    print("\nUSERNAME")
    print(result)

    # --------------------------------------------------------
    # Test profile name
    # --------------------------------------------------------

    result = await resolve_memory(
        session_id,
        "what is my name",
    )

    print("\nNAME")
    print(result)

    # --------------------------------------------------------
    # Test repository
    # --------------------------------------------------------

    result = await resolve_memory(
        session_id,
        "what repository are we working on",
    )

    print("\nREPOSITORY")
    print(result)

    # --------------------------------------------------------
    # Test file
    # --------------------------------------------------------

    result = await resolve_memory(
        session_id,
        "what file did we analyze",
    )

    print("\nFILE")
    print(result)

    # --------------------------------------------------------
    # Test unknown question
    # --------------------------------------------------------

    result = await resolve_memory(
        session_id,
        "analyze the authentication code",
    )

    print("\nUNKNOWN")
    print(result)

    await memory.close()


if __name__ == "__main__":
    asyncio.run(main())