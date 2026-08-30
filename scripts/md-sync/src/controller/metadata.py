def drop_empty(value):
    if isinstance(value, dict):
        return {k: drop_empty(v) for k, v in value.items() if v not in (None, "", [])}
    if isinstance(value, list):
        return [drop_empty(v) for v in value if v not in (None, "", [])]
    return value
