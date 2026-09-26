async def resolve_memory(
    session_id: str,
    query: str,
):
    # Redis memory is disabled for deployment.
    # Let the normal agent workflow handle the query.
    return {
        "handled": False,
    }