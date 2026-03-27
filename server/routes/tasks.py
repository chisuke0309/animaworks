import logging
from typing import Any
from fastapi import APIRouter

from core.paths import get_animas_dir
from core.memory.task_queue import TaskQueueManager
from core.memory.activity import ActivityLogger

logger = logging.getLogger("animaworks.server.api.tasks")

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def list_tasks() -> list[dict[str, Any]]:
    """List root tasks grouped by root_task_id, deduplicated.

    Returns one entry per root_task_id (the assignee's own entry preferred).
    Each entry includes a 'sub_tasks' list of child tasks sharing the same root.
    """
    animas_dir = get_animas_dir()
    tasks_by_id: dict[str, dict[str, Any]] = {}

    if not animas_dir.exists():
        return []

    for d in animas_dir.iterdir():
        if not d.is_dir():
            continue
        try:
            tqm = TaskQueueManager(d)
            for task in tqm.list_tasks():
                t_dict = task.model_dump()
                t_dict["anima_id"] = d.name
                tid = t_dict["task_id"]
                # Keep the entry from the assignee's own queue when duplicated
                if tid not in tasks_by_id or d.name == task.assignee:
                    tasks_by_id[tid] = t_dict
        except Exception as e:
            logger.warning("Failed to scan tasks for Anima %s: %s", d.name, e)

    # Infer delegator from anima_id when relay_chain is missing (legacy data)
    for t in tasks_by_id.values():
        if not t.get("relay_chain") and t.get("anima_id") and t["anima_id"] != t.get("assignee"):
            t["relay_chain"] = [t["anima_id"]]

    all_tasks = list(tasks_by_id.values())

    # ── Group by root_task_id ──
    # root_task_id=None means legacy data; treat task_id as its own root.
    roots: dict[str, dict[str, Any]] = {}
    children: dict[str, list[dict[str, Any]]] = {}

    for t in all_tasks:
        root_id = t.get("root_task_id") or t["task_id"]
        t["root_task_id"] = root_id  # normalise None → self

        if t["task_id"] == root_id:
            # This task IS the root (first task in the chain, or standalone)
            if root_id not in roots:
                roots[root_id] = t
            elif t.get("ts", "") > roots[root_id].get("ts", ""):
                # prefer most recent if duplicate root_id somehow
                pass
        else:
            children.setdefault(root_id, []).append(t)

    # Attach sub_tasks to each root and compute effective status
    result = []
    for root_id, root in roots.items():
        subs = sorted(
            children.get(root_id, []),
            key=lambda x: x.get("ts", ""),
        )
        root["sub_tasks"] = subs
        result.append(root)

    result.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return result


@router.get("/{task_id}/messages")
def get_task_messages(task_id: str) -> list[dict[str, Any]]:
    """Get the full timeline for a task (or its entire pipeline via root_task_id).

    Returns three kinds of events in chronological order:
    - instruction: the original delegation instruction (synthesized from task data)
    - status_update: task_updated activity log entries
    - message: message_sent / message_received entries with matching task_id
    """
    animas_dir = get_animas_dir()
    events: list[dict[str, Any]] = []

    if not animas_dir.exists():
        return events

    # ── Step 1: Collect all tasks that share the same root_task_id ──
    tasks_by_id: dict[str, dict[str, Any]] = {}
    for d in animas_dir.iterdir():
        if not d.is_dir():
            continue
        try:
            tqm = TaskQueueManager(d)
            for task in tqm.list_tasks():
                t_dict = task.model_dump()
                t_dict["anima_id"] = d.name
                tid = t_dict["task_id"]
                if tid not in tasks_by_id or d.name == task.assignee:
                    tasks_by_id[tid] = t_dict
        except Exception:
            pass

    # Find the requested task (may be root or child)
    requested = tasks_by_id.get(task_id)
    if not requested:
        return []

    root_id = requested.get("root_task_id") or task_id

    # Collect all task_ids in this pipeline (same root)
    pipeline_task_ids: set[str] = set()
    for t in tasks_by_id.values():
        t_root = t.get("root_task_id") or t["task_id"]
        if t_root == root_id:
            pipeline_task_ids.add(t["task_id"])

    # ── Step 2: Synthesize instruction events for each task in order ──
    pipeline_tasks = [
        t for t in tasks_by_id.values()
        if (t.get("root_task_id") or t["task_id"]) == root_id
        # Exclude delegated tracking entries to avoid duplicate instructions
        and t.get("status") != "delegated"
    ]
    pipeline_tasks.sort(key=lambda x: x.get("ts", ""))

    for task in pipeline_tasks:
        ts = task.get("ts", "")
        relay = task.get("relay_chain") or []
        delegator = relay[0] if relay else ("cicchi" if task.get("source") == "anima" else "User")
        events.append({
            "ts": ts,
            "event_kind": "instruction",
            "from_person": delegator,
            "to_person": task.get("assignee", ""),
            "content": task.get("original_instruction", ""),
            "task_id": task["task_id"],
        })

    # ── Step 3: Collect activity log events for all pipeline task_ids ──
    seen: set[tuple] = set()
    for d in animas_dir.iterdir():
        if not d.is_dir():
            continue
        try:
            activity = ActivityLogger(d)
            recent = activity.recent(
                days=30,
                limit=2000,
                types=["task_updated", "message_sent", "message_received", "task_delegated"],
            )
            for e in recent:
                if not e.meta or e.meta.get("task_id") not in pipeline_task_ids:
                    continue
                e_dict = e.to_api_dict()
                key = (e_dict.get("ts"), e_dict.get("type"), (e_dict.get("content") or "")[:80])
                if key in seen:
                    continue
                seen.add(key)

                if e.type == "task_updated":
                    status = e.meta.get("status", "")
                    e_dict["event_kind"] = "status_update"
                    e_dict["status"] = status
                elif e.type == "task_delegated":
                    e_dict["event_kind"] = "instruction"
                else:
                    e_dict["event_kind"] = "message"

                events.append(e_dict)
        except Exception as exc:
            logger.warning("Failed to scan activity logs for Anima %s: %s", d.name, exc)

    events.sort(key=lambda x: x.get("ts", ""))
    return events
