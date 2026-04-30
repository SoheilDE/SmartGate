def validate(response: dict) -> bool:
    """Return True if the response conforms to the OpenAI chat completion schema."""
    try:
        choices = response.get("choices")
        if not choices or not isinstance(choices, list):
            return False
        first = choices[0]
        message = first.get("message", {})
        if not message.get("content"):
            return False
        if first.get("finish_reason") == "error":
            return False
        if "usage" not in response:
            return False
        return True
    except Exception:
        return False
