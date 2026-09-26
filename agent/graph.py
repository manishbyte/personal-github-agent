from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agent.state import AgentState
from agent.nodes import (
    memory_node,
    direct_response_node,
    intent_node,
    profile_node,
    repository_node,
    file_content_node,
    repository_structure_node,
    response_node,
    route_intent,
)
from agent.issue_nodes import (
    file_analysis_node,
    issue_proposal_node,
    issue_approval_node,
    create_issue_node,
    issue_response_node,
    route_issue_approval,
)


def route_memory(state: AgentState):
    if state.get("memory_handled") is True:
        return "direct_response"
    return "intent"


def route_after_file_content(state: AgentState):
    intent = state.get("intent")

    if intent in {
        "file_analysis",
        "analyze_and_create_issue",
    }:
        return "file_analysis"

    return "response"


def route_after_analysis(state: AgentState):
    if state.get("intent") == "analyze_and_create_issue":
        return "issue_proposal"

    return "response"


def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("memory", memory_node)
    workflow.add_node("direct_response", direct_response_node)
    workflow.add_node("intent", intent_node)
    workflow.add_node("profile", profile_node)
    workflow.add_node("repositories", repository_node)
    workflow.add_node("file_content", file_content_node)
    workflow.add_node("file_analysis", file_analysis_node)
    workflow.add_node("structure", repository_structure_node)
    workflow.add_node("response", response_node)
    workflow.add_node("issue_proposal", issue_proposal_node)
    workflow.add_node("issue_approval", issue_approval_node)
    workflow.add_node("create_issue", create_issue_node)
    workflow.add_node("issue_response", issue_response_node)

    workflow.add_edge(START, "memory")

    workflow.add_conditional_edges(
        "memory",
        route_memory,
        {
            "direct_response": "direct_response",
            "intent": "intent",
        },
    )

    workflow.add_edge("direct_response", END)

    workflow.add_conditional_edges(
        "intent",
        route_intent,
        {
            "profile": "profile",
            "repositories": "repositories",
            "file_content": "file_content",
            "structure": "structure",
            "issue_proposal": "issue_proposal",
            "response": "response",
        },
    )

    workflow.add_edge("profile", "response")
    workflow.add_edge("repositories", "response")
    workflow.add_edge("structure", "response")

    workflow.add_conditional_edges(
        "file_content",
        route_after_file_content,
        {
            "file_analysis": "file_analysis",
            "response": "response",
        },
    )

    workflow.add_conditional_edges(
        "file_analysis",
        route_after_analysis,
        {
            "issue_proposal": "issue_proposal",
            "response": "response",
        },
    )

    workflow.add_edge("issue_proposal", "issue_approval")

    workflow.add_conditional_edges(
        "issue_approval",
        route_issue_approval,
        {
            "create_issue": "create_issue",
            "issue_response": "issue_response",
        },
    )

    workflow.add_edge("create_issue", END)
    workflow.add_edge("issue_response", END)
    workflow.add_edge("response", END)

    checkpoint = MemorySaver()

    return workflow.compile(
        checkpointer=checkpoint
    )
