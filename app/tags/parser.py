import re
from dataclasses import dataclass, field

# Matches </tag1,tag2> at the very start of the message content
_TAG_RE = re.compile(r'^\s*<\/([^>]+)>\s*')


@dataclass
class TagOverrides:
    tier: str | None = None           # force a specific model tier
    skip_cache: bool = False          # no-cache tag
    skip_fallback: bool = False       # no-fallback tag
    force_stream: bool | None = None  # stream / no-stream tag
    tags_found: list[str] = field(default_factory=list)


def parse(messages: list[dict]) -> tuple[list[dict], TagOverrides]:
    """
    Find and strip </tag,...> from the start of the last user message.

    Returns (clean_messages, overrides). If no tag is found the original
    messages list and an empty TagOverrides are returned unchanged.
    """
    overrides = TagOverrides()
    if not messages:
        return messages, overrides

    last_user_idx = next(
        (i for i in range(len(messages) - 1, -1, -1) if messages[i].get("role") == "user"),
        None,
    )
    if last_user_idx is None:
        return messages, overrides

    content = messages[last_user_idx].get("content", "")
    match = _TAG_RE.match(content)
    if not match:
        return messages, overrides

    for raw in match.group(1).split(","):
        tag = raw.strip().lower()
        if not tag:
            continue
        overrides.tags_found.append(tag)
        if tag == "no-cache":
            overrides.skip_cache = True
        elif tag == "no-fallback":
            overrides.skip_fallback = True
        elif tag == "stream":
            overrides.force_stream = True
        elif tag == "no-stream":
            overrides.force_stream = False
        else:
            overrides.tier = tag  # anything else is treated as a model tier name

    clean_messages = list(messages)
    clean_messages[last_user_idx] = {
        **messages[last_user_idx],
        "content": content[match.end():],
    }
    return clean_messages, overrides
