"""Même résultat que rules.blocks, sans matérialiser tous les frères précédents."""

from rules import role


def blocks(source, document):
    output = []
    for di, xp in enumerate(document["divisions"]):
        node = source.node(xp)
        first_p = node.find("p")
        for child in node:
            if not isinstance(child.tag, str):
                continue
            a, b = source.span(child)
            if b <= document["start"] or a >= document["end"] or child.tag.startswith("div"):
                continue
            output.append(
                dict(
                    xpath=source.tree.getpath(child),
                    division=di,
                    tag=child.tag,
                    start=max(a, document["start"]),
                    end=min(b, document["end"]),
                    role=role(child, first=child is first_p),
                    line=child.sourceline,
                )
            )
    return sorted(output, key=lambda b: (b["start"], b["end"]))


def cache_nodes(source):
    nodes = {source.tree.getpath(n): n for n in source.tree.iter() if isinstance(n.tag, str)}
    spans = {node: source.ranges[xp] for xp, node in nodes.items()}
    source.node = lambda xp: nodes[xp]
    source.span = lambda node: spans[node]
