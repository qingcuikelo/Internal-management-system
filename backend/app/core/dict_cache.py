import json


def _key(dict_type: str) -> str:
    return f"dict:{dict_type}"


def get_cached(redis, dict_type: str) -> list[dict] | None:
    raw = redis.get(_key(dict_type))
    return json.loads(raw) if raw else None


def set_cached(redis, dict_type: str, items: list[dict], ttl: int) -> None:
    redis.set(_key(dict_type), json.dumps(items, ensure_ascii=False), ex=ttl)


def invalidate(redis, dict_type: str) -> None:
    redis.delete(_key(dict_type))
