from collections import defaultdict


def descendant_ids(rows: list[tuple[str, str | None]], root_id: str) -> set[str]:
    children: dict[str | None, list[str]] = defaultdict(list)
    for node_id, parent_id in rows:
        children[parent_id].append(node_id)

    result: set[str] = {root_id}
    stack = [root_id]
    while stack:
        current = stack.pop()
        for child in children.get(current, []):
            if child not in result:
                result.add(child)
                stack.append(child)
    return result
