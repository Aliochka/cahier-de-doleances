"""Zones continues et candidats source fixés AVANT finalisation du détecteur V2."""

import datetime
import re

from common import HERE, PILOT, V1, compact, jlines, rows, sha, sources, write


def draw(value):
    return sha("validation-v2-1789|" + value)


def main():
    assert not (HERE / "validation-plan.json").exists()
    ss = sources()
    old = rows(PILOT / "data/documents.jsonl")
    selected = rows(V1 / "data/selection.jsonl")
    neg = rows(V1 / "data/non-detection-windows.jsonl")
    zones = []
    candidates = []
    excluded = []
    for v, s in ss.items():
        used = (
            {c["xpath"] for c in selected if c["volume"] == v}
            | {xp for d in old if d["volume"] == v for xp in d["divisions"]}
            | {w["xpaths"][0].rsplit("/p", 1)[0] for w in neg if w["volume"] == v}
        )
        if v == 5:
            used.add("/TEI.2/text/body/div1/div2[1]/div3[3]")
        excluded.extend(
            dict(
                volume=v,
                xpath=xp,
                reason="prior selected/development/negative-context inspected; conservative whole-division exclusion",
            )
            for xp in sorted(used)
        )
        leaves = s.tree.xpath(
            '//text/body//*[starts-with(local-name(),"div")][p and not(*[starts-with(local-name(),"div")])]'
        )
        pairs = []
        for i, n in enumerate(leaves[:-1]):
            m = leaves[i + 1]
            x, y = s.tree.getpath(n), s.tree.getpath(m)
            a, b = s.span(n)[0], s.span(m)[1]
            if x in used or y in used or not 400 < b - a < 16000:
                continue
            pairs.append(
                dict(volume=v, start=a, end=b, xpaths=[x, y], key=draw(f"zone|{v}|{x}|{y}"))
            )
        pairs.sort(key=lambda z: z["key"])
        chosen = []
        for z in pairs:
            if any(z["start"] < p["end"] and z["end"] > p["start"] for p in chosen):
                continue
            chosen.append(z)
            if len(chosen) == 2:
                break
        assert len(chosen) == 2, v
        for i, z in enumerate(chosen, 1):
            z["id"] = f"zone-v{v}-{i}"
            z["text"] = s.text[z["start"] : z["end"]]
            zones.append(z)
        fresh = []
        for n in leaves:
            xp = s.tree.getpath(n)
            a, b = s.span(n)
            if xp in used or b - a > 65000 or any(a < z["end"] and b > z["start"] for z in chosen):
                continue
            title = " | ".join(compact(h) for h in n.findall("head"))
            opening = " ".join(compact(p) for p in n.findall("p")[:2])
            if not re.search(
                r"cahier|dol[ée]ance|plaint|remontr|instruction|mandat|m[ée]moire|extrait|proc[èeé]s|pouvoir|chapitre",
                title + " " + opening,
                re.I,
            ):
                continue
            strong = bool(
                re.search(
                    r"cahier|instruction|mandat|dol[ée]ance|remontr",
                    title + " " + opening[:200],
                    re.I,
                )
            )
            fresh.append(
                dict(
                    id="validation-" + sha(f"{s.sha256}|{xp}")[:20],
                    volume=v,
                    xpath=xp,
                    start=a,
                    end=b,
                    title=title,
                    length=b - a,
                    strong_lexical_hint=strong,
                )
            )
        cells = [
            ("strong_short", lambda c: c["strong_lexical_hint"] and c["length"] < 16000),
            ("alternative", lambda c: not c["strong_lexical_hint"]),
            ("strong_long", lambda c: c["strong_lexical_hint"] and c["length"] >= 16000),
            ("remaining", lambda c: True),
        ]
        selected_here = []
        for name, predicate in cells:
            eligible = [c for c in fresh if predicate(c) and c not in selected_here] or [
                c for c in fresh if c not in selected_here
            ]
            assert eligible, (v, name)
            c = min(eligible, key=lambda c: draw(name + "|" + c["id"]))
            c["selection_stratum"] = name
            selected_here.append(c)
        candidates.extend(selected_here)
    jlines(HERE / "data/validation-zones.jsonl", zones)
    jlines(HERE / "data/validation-candidates.jsonl", candidates)
    write(HERE / "data/validation-exclusions.json", excluded)
    write(
        HERE / "validation-plan.json",
        dict(
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            rules_finalized=False,
            reference_created=False,
            candidates=24,
            zones=12,
            candidate_method="4 raw structural candidates/volume by SHA order in strong-short, alternative, strong-long, remaining strata; no V2 predictions",
            zone_method="2 disjoint complete consecutive-leaf intervals/volume, 400..16000 decoded characters, hash selection independently of detector",
            selection_seed="validation-v2-1789",
            prior_170_candidates_excluded=True,
            prior_30_parents_excluded=True,
            prior_negative_enclosing_divisions_excluded=True,
            pecqueuse_excluded=True,
            statistically_representative=False,
            judge="Codex, not independent human",
            files={
                n: sha((HERE / n).read_bytes())
                for n in [
                    "data/validation-zones.jsonl",
                    "data/validation-candidates.jsonl",
                    "data/validation-exclusions.json",
                ]
            },
        ),
    )
    print("Fixed24 unseen source candidates and12 continuous zones; V2 rules not yet finalized")


if __name__ == "__main__":
    main()
