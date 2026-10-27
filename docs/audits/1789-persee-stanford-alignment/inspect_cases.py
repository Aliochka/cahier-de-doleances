"""Dossiers de contrôle ciblés sur les sources Stanford seules, aucune correction automatique."""

from alignment import page_index
from auditlib import HERE, compact, load_sources

CASES = [
    (2, "/TEI.2/text/body/div1/div2[23]/div3[3]"),
    (2, "/TEI.2/text/body/div1/div2[18]/div3[1]"),
    (3, "/TEI.2/text/body/div1/div2[52]/div3[3]"),
    (3, "/TEI.2/text/body/div1/div2[37]/div3[3]"),
    (3, "/TEI.2/text/body/div1/div2[50]/div3[5]"),
    (4, "/TEI.2/text/body/div1/div2[18]/div3[170]"),
    (5, "/TEI.2/text/body/div1/div2[1]/div3[77]"),
    (6, "/TEI.2/text/body/div1/div2[2]/div3[4]"),
]


def main():
    ss = load_sources()
    lines = []
    for v, path in CASES:
        s = ss[v]
        _, at = page_index(s)
        n = s.node(path)
        ps = n.findall("p")
        lines.append(f"\nCASE {v} {path}\n")
        for i, p in enumerate(ps, 1):
            text = compact(p)
            a, b = s.span(p)
            # Show all paragraph starts, as well as complete short headings and transitions.
            lines.append(f"p[{i}] pg{at(a)['page']} [{a},{b}) " + text[:160] + "\n")
    (HERE / ".cache/case-boundaries.txt").write_text("".join(lines))
    n = ss[6].tree.xpath('//head[contains(.,"Autun") or contains(.,"AUTUN")]')
    (HERE / ".cache/autun-lists.txt").write_text(
        "\n".join(ss[6].tree.getpath(h) + " " + compact(h) for h in n)
    )


if __name__ == "__main__":
    main()
