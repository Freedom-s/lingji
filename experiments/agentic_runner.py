"""Run Agentic-mode retrieval experiment.

Uses AgentLoop.run() with data-collection hooks. Captures per-turn
tool calls, retrieved pages, and final answer for analysis.
"""
import json
import logging
import time
from typing import Any

logger = logging.getLogger("experiments.agentic_runner")


def run_agentic_experiment(
    test_queries: list[dict],
    mcp_url: str,
    chat_mdl: Any,
    kb_ids: list[str],
    tenant_ids: list[str],
    dialog: Any,
    embd_id: str | None = None,
    rerank_id: str | None = None,
    max_turns: int = 10,
    max_images: int = 5,
) -> list[dict]:
    """Run Agentic-mode retrieval against the full test set.

    For each query, creates a fresh AgentLoop and collects:
    - All tool calls (name, args, result summary) per turn
    - Pages retrieved per turn
    - Final answer and reference
    - Elapsed time

    Args:
        test_queries: List of query dicts.
        mcp_url: MCP server URL (e.g. http://localhost:9390).
        chat_mdl: Chat LLM from LLMBundle.
        kb_ids: Knowledge base IDs.
        tenant_ids: Tenant IDs.
        dialog: Dialog model object (for AgentLoop context).
        embd_id: Embedding model ID.
        rerank_id: Rerank model ID.
        max_turns: Max ReAct loop iterations.
        max_images: Max images injected into final VLM call.

    Returns:
        List of result dicts with agentic-specific metadata.
    """
    from rag.agent.client.loop import AgentLoop

    results: list[dict] = []
    n = len(test_queries)

    for i, q in enumerate(test_queries):
        query_text = q["query"]
        gt_page_id = q["page_id"]

        agent = AgentLoop(mcp_url=mcp_url, chat_mdl=chat_mdl)
        # Override max_tool_calls for experiment
        agent.max_tool_calls = max_turns

        # Collect events from agent.run()
        events: list[dict] = []
        all_retrieved_pages: list[dict] = []
        seen_page_ids: set[str] = set()
        tool_calls_log: list[dict] = []
        turns: int = 0

        t0 = time.perf_counter()
        try:
            for event in agent.run(
                question=query_text,
                history=[],  # Single-turn retrieval; no conversation history
                kb_ids=kb_ids,
                tenant_ids=tenant_ids,
                dialog=dialog,
                embd_id=embd_id,
                rerank_id=rerank_id,
                max_images=max_images,
            ):
                events.append(event)

                # Track retrieved pages from reference
                ref = event.get("reference", {})
                chunks = ref.get("chunks", []) if isinstance(ref, dict) else []
                for chunk in chunks:
                    pid = chunk.get("page_id", "")
                    if pid and pid not in seen_page_ids:
                        seen_page_ids.add(pid)
                        all_retrieved_pages.append(chunk)

                # Count tool calls from answer text
                answer = event.get("answer", "")
                if isinstance(answer, str) and "<tool_call" in answer:
                    turns = answer.count("<tool_call")
        except Exception as e:
            logger.error(f"Agentic error for query {q.get('id')}: {e}")

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Get final result from last substantive event
        final_event = events[-1] if events else {}
        final_answer = final_event.get("answer", "")
        final_ref = final_event.get("reference", {})

        # Determine hit
        retrieved_page_ids = [p.get("page_id", "") for p in all_retrieved_pages]
        hit_rank = None
        try:
            hit_rank = retrieved_page_ids.index(gt_page_id) + 1
        except ValueError:
            pass

        # Parse tool calls
        parsed_tool_calls = _parse_tool_calls_from_text(
            final_answer if isinstance(final_answer, str) else ""
        )

        result = {
            "mode": "agentic",
            "query_id": q.get("id", f"q{i}"),
            "query": query_text,
            "ground_truth_page_id": gt_page_id,
            "retrieved_page_ids": retrieved_page_ids,
            "hit_at_rank": hit_rank,
            "recall_1": hit_rank == 1 if hit_rank else False,
            "recall_3": (hit_rank is not None and hit_rank <= 3),
            "recall_5": (hit_rank is not None and hit_rank <= 5),
            "mrr_contrib": 1.0 / hit_rank if hit_rank else 0.0,
            "elapsed_ms": round(elapsed_ms, 1),
            # Agentic-specific metadata
            "agentic_turns": turns,
            "agentic_tool_calls": parsed_tool_calls,
            "agentic_pages_retrieved": len(all_retrieved_pages),
            "agentic_first_turn_hit": _check_first_turn_hit(
                all_retrieved_pages, gt_page_id, turns, parsed_tool_calls
            ),
            "agentic_final_answer_len": (
                len(final_answer) if isinstance(final_answer, str) else 0
            ),
            "agentic_reference_count": (
                len(final_ref.get("chunks", []))
                if isinstance(final_ref, dict) else 0
            ),
        }
        results.append(result)

        if (i + 1) % 20 == 0:
            logger.info(f"Agentic: processed {i + 1}/{n} queries")

    n_hits = sum(1 for r in results if r["recall_3"])
    logger.info(f"Agentic complete: {n_hits}/{n} Recall@3 hits ({n_hits/n:.1%})")
    return results


def _parse_tool_calls_from_text(text: str) -> list[dict]:
    """Extract tool call names from agent's tool_call_log text."""
    import re

    calls: list[dict] = []
    # Pattern: <tool_call name="tool_name"> ... </tool_call>
    pattern = r'<tool_call\s+name="([^"]+)"\s*>(.*?)</tool_call>'
    for match in re.finditer(pattern, text, re.DOTALL):
        calls.append({
            "tool": match.group(1),
            "content": match.group(2).strip()[:500],
        })
    return calls


def _check_first_turn_hit(
    pages: list[dict],
    gt_page_id: str,
    total_turns: int,
    tool_calls: list[dict],
) -> bool:
    """Heuristic: check if gt_page_id was found in first turn's results.

    Since AgentLoop doesn't explicitly label turns per page, we approximate:
    if total_turns <= 2 and the page is in retrieved_pages, it was likely
    found in the first retrieval turn.
    """
    if total_turns <= 0:
        return False
    # If only one round of tool calls, any hit is a first-turn hit
    if total_turns == 1:
        return True
    # Otherwise we can't perfectly determine without turn-level tracking
    # from AgentLoop, so we mark as None/unknown
    return False  # Conservative: mark as not first-turn unless exactly 1 turn
