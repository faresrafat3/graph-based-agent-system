"""
Shared Karpathy Loop workflow factory.

Every agent graph in this repo follows the same five-node lifecycle:

    propose -> execute -> evaluate -> (commit | refine -> propose | escalate)

The per-agent variance is almost entirely in ``execute`` (and sometimes
``propose``/``evaluate``/``commit``/``refine``); the graph wiring, the compile
step, and the standard node implementations were previously copy-pasted into
each agent module. This module provides them once:

* :func:`build_karpathy_loop` — wires and compiles the five-node StateGraph.
* Standard node implementations (:func:`standard_propose`,
  :func:`standard_evaluate`, :func:`standard_commit`, :func:`standard_refine`,
  :func:`standard_should_continue`) that agents can use directly or as the
  building blocks of thin per-agent wrappers.

Behavior contract (preserved from the original per-agent copies):

* ``propose`` validates declared input keys (default: none) and seeds breaches.
* ``execute`` is always agent-supplied.
* ``evaluate`` succeeds iff none of the declared fail keys are non-empty
  (default: ``breaches``).
* ``commit`` is terminal and returns ``{"committed": True}`` (the key is not in
  most state schemas; LangGraph tolerates and ignores it).
* ``refine`` bumps ``retry_count`` and marks the loop not-successful.
* ``should_continue`` routes commit/escalate/refine, escalating once
  ``retry_count >= retry_cap``.
"""

from typing import Any, Callable, Optional, Tuple, Type

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

#: A TypedDict subclass used as a LangGraph state schema.
StateType = Type[dict]

#: A node function: pure ``(state) -> partial-state-dict`` transition.
NodeFn = Callable[[dict], dict]

#: A routing function: ``(state) -> next-node-name``.
RouteFn = Callable[[dict], str]


def standard_propose(state: dict, list_input_keys: Tuple[str, ...] = ()) -> dict:
    """Step 1 default: validate that declared input keys are lists.

    Mirrors the original per-agent propose bodies (e.g. ``disputes must be a
    list.``). A missing key defaults to ``[]`` and therefore passes, exactly
    like the original ``state.get(key, [])`` checks.
    """
    for key in list_input_keys:
        if not isinstance(state.get(key, []), list):
            return {"breaches": [f"{key} must be a list."], "success": False}
    return {"breaches": [], "success": True}


def standard_evaluate(state: dict, fail_keys: Tuple[str, ...] = ("breaches",)) -> dict:
    """Step 3 default: success iff none of the declared fail keys are non-empty.

    Mirrors the original ``{"success": len(state.get("breaches", [])) == 0}``
    bodies, generalised so an agent whose failure key is named differently
    (e.g. ``conflicts``) can reuse it.
    """
    failed = any(state.get(key) for key in fail_keys)
    return {"success": not failed}


def standard_commit(state: dict) -> dict:
    """Step 4 default: the loop reached the terminal commit node."""
    return {"committed": True}


def standard_refine(state: dict) -> dict:
    """Step 5 default: bump the retry counter and mark the loop unsuccessful."""
    return {"retry_count": state.get("retry_count", 0) + 1, "success": False}


def standard_should_continue(state: dict, retry_cap: int = 1) -> str:
    """Default routing: commit on success, escalate past the cap, else refine."""
    if state.get("success", False):
        return "commit"
    if state.get("retry_count", 0) >= retry_cap:
        return "escalate"
    return "refine"


def build_karpathy_loop(
    state_type: StateType,
    *,
    execute_fn: NodeFn,
    propose_fn: Optional[NodeFn] = None,
    evaluate_fn: Optional[NodeFn] = None,
    commit_fn: Optional[NodeFn] = None,
    refine_fn: Optional[NodeFn] = None,
    should_continue_fn: Optional[RouteFn] = None,
    retry_cap: int = 1,
    list_input_keys: Tuple[str, ...] = (),
    evaluate_fail_keys: Tuple[str, ...] = ("breaches",),
    include_refine: bool = True,
) -> Any:
    """Wire and compile the standard five-node Karpathy Loop LangGraph.

    Args:
        state_type: The agent's TypedDict state schema.
        execute_fn: The agent's execute node (required — this is where the
            real work happens).
        propose_fn: Override for the propose node. Defaults to
            :func:`standard_propose` with ``list_input_keys``.
        evaluate_fn: Override for the evaluate node. Defaults to
            :func:`standard_evaluate` with ``evaluate_fail_keys``.
        commit_fn: Override for the commit node. Defaults to
            :func:`standard_commit`.
        refine_fn: Override for the refine node. Defaults to
            :func:`standard_refine`.
        should_continue_fn: Override for the routing function. Defaults to
            :func:`standard_should_continue` with ``retry_cap``.
        retry_cap: Number of allowed refine retries before escalating
            (used by the default router only).
        list_input_keys: Input keys validated as lists by the default propose.
        evaluate_fail_keys: State keys whose non-emptiness fails the default
            evaluate.
        include_refine: False for agents whose loop has no refine edge (only
            human_escalation), which then routes evaluate straight to
            commit/escalate.

    Returns:
        A compiled LangGraph ready for ``invoke`` (checkpointer is a fresh
        in-process ``MemorySaver``, matching the original per-agent graphs).
    """
    propose = propose_fn or (lambda state: standard_propose(state, list_input_keys))
    evaluate = evaluate_fn or (lambda state: standard_evaluate(state, evaluate_fail_keys))
    commit = commit_fn or standard_commit
    refine = refine_fn or standard_refine
    route = should_continue_fn or (lambda state: standard_should_continue(state, retry_cap=retry_cap))

    workflow = StateGraph(state_type)
    workflow.add_node("propose", propose)
    workflow.add_node("execute", execute_fn)
    workflow.add_node("evaluate", evaluate)
    workflow.add_node("commit", commit)
    if include_refine:
        workflow.add_node("refine", refine)
    workflow.set_entry_point("propose")
    workflow.add_edge("propose", "execute")
    workflow.add_edge("execute", "evaluate")
    if include_refine:
        workflow.add_conditional_edges(
            "evaluate",
            route,
            {"commit": "commit", "refine": "refine", "escalate": END},
        )
        workflow.add_edge("refine", "propose")
    else:
        workflow.add_conditional_edges(
            "evaluate",
            route,
            {"commit": "commit", "escalate": END},
        )
    workflow.add_edge("commit", END)

    return workflow.compile(checkpointer=MemorySaver())
