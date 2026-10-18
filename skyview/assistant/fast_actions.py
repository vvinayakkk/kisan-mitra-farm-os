"""Narrow, deterministic commands; anything ambiguous stays with the agent.

Only an explicit single task title and ISO date qualify. This does not guess
arguments, process attachments, interpret quoted instructions or authorize edits.
"""

import re

from .models import TaskArgs


def task_command(request):
    if (
        request.attachment_ids
        or request.answers
        or request.approval is not None
        or request.mission_id
        or request.language not in (None, "en")
    ):
        return None
    match = re.fullmatch(
        r"(?:please\s+)?(?:add|create|save|schedule)\s+(?:a\s+)?task\s+(?:called|named)\s+(.{1,160}?)\s+on\s+(\d{4}-\d{2}-\d{2})[.!]?\s*",
        request.message.strip(),
        re.IGNORECASE,
    )
    if not match:
        return None
    title = match[1].strip().strip('"')
    # Compound, conditional, or additional instructions need semantic routing.
    if re.search(
        r"\b(?:and|then|unless|if|but|except|instead|not)\b|[\n;]", title, re.IGNORECASE
    ):
        return None
    try:
        return TaskArgs(title=title, due_date=match[2]).model_dump(mode="json")
    except ValueError:
        return None
