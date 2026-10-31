"""Corrige une fuite de nouveauté sans retirer l'ancien cas ni changer les règles."""

import datetime
import re

from common import CACHE, HERE, PILOT, V1, compact, jlines, read, rows, sha, sources, write


def main():
    assert not (HERE / "novelty-amendment.json").exists()
    ss = sources()
    cs = rows(HERE / "data/validation-candidates.jsonl")
    zones = rows(HERE / "data/validation-zones.jsonl")
    known = read(PILOT / "negative-cases.json")
    leaks = [
        c for c in cs if any(c["volume"] == n["volume"] and c["xpath"] == n["xpath"] for n in known)
    ]
    assert len(leaks) == 1 and leaks[0]["id"] == "validation-7f38a827548ffdb56929"
    reserves = []
    for leak in leaks:
        v = 2
        s = ss[v]  # Volume I has no further eligible fresh candidate in this frame.
        used = (
            {c["xpath"] for c in rows(V1 / "data/selection.jsonl") if c["volume"] == v}
            | {
                xp
                for d in rows(PILOT / "data/documents.jsonl")
                if d["volume"] == v
                for xp in d["divisions"]
            }
            | {
                w["xpaths"][0].rsplit("/p", 1)[0]
                for w in rows(V1 / "data/non-detection-windows.jsonl")
                if w["volume"] == v
            }
            | {c["xpath"] for c in cs if c["volume"] == v}
            | {n["xpath"] for n in known if n["volume"] == v}
        )
        frame = []
        for node in s.tree.xpath(
            '//text/body//*[starts-with(local-name(),"div")][p and not(*[starts-with(local-name(),"div")])]'
        ):
            xp = s.tree.getpath(node)
            a, b = s.span(node)
            if (
                xp in used
                or b - a > 65000
                or any(a < z["end"] and b > z["start"] for z in zones if z["volume"] == v)
            ):
                continue
            title = " | ".join(compact(h) for h in node.findall("head"))
            opening = " ".join(compact(p) for p in node.findall("p")[:2])
            if not re.search(
                r"cahier|dol[ée]ance|plaint|remontr|instruction|mandat|m[ée]moire|extrait|proc[èeé]s|pouvoir|chapitre",
                title + " " + opening,
                re.I,
            ):
                continue
            cid = "validation-" + sha(f"{s.sha256}|{xp}")[:20]
            frame.append(
                dict(
                    id=cid,
                    volume=v,
                    xpath=xp,
                    start=a,
                    end=b,
                    title=title,
                    length=b - a,
                    selection_stratum="novelty_reserve_hash_addition",
                )
            )
        c = min(frame, key=lambda c: sha("validation-v2-1789|reserve|" + c["id"]))
        reserves.append(c)
        node = s.node(c["xpath"])
        ps = node.findall("p")
        lines = [f"CANDIDATE {c['id']} {c['xpath']}\n"]
        lines += ["HEAD " + compact(h) + "\n" for h in node.findall("head")]
        indices = sorted(
            set(
                list(range(min(10, len(ps))))
                + list(range(max(0, len(ps) - 4), len(ps)))
                + [i for i, p in enumerate(ps) if len(compact(p)) < 120]
            )
        )
        lines += [f"p[{i + 1}] " + compact(ps[i]) + "\n" for i in indices]
        (CACHE / f"candidate-reserve-v{v}.txt").write_text("".join(lines))
    jlines(HERE / "data/validation-candidates-reserve.jsonl", reserves)
    write(
        HERE / "novelty-amendment.json",
        dict(
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            reason="Pilot negative Albret was omitted from initial whole-division novelty exclusions. Discovered on source read, before predictions. Kept as legacy control, excluded from unseen metrics.",
            legacy_controls=[c["id"] for c in leaks],
            added_candidates=[c["id"] for c in reserves],
            total_registered_candidates=25,
            truly_unseen_candidates=24,
            zones_unchanged=12,
            models_or_thresholds_changed=False,
            selection="same raw lexical frame; fresh deterministic reserve hash, no predictions used",
            file_sha256=sha((HERE / "data/validation-candidates-reserve.jsonl").read_bytes()),
        ),
    )
    print(
        "Original25 registered with reserve:24 unseen +1 retained legacy control; rules unchanged"
    )


if __name__ == "__main__":
    main()
