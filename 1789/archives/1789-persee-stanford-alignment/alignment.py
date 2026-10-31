"""Rapprochement expérimental limité; ne certifie jamais une frontière automatiquement."""

import bisect
import difflib
import re

from auditlib import HERE, compact, fold, jlines, load_sources, rows, save, source_ref

STOP = set(
    "de des du la le les leaf_record d a au aux et en pour par cahier cahiers doleances plaintes remontrances habitants assemblee etat etats generaux bailliage senechaussee paroisse communaute ville village pays province ordre royaume demandes instructions tiers".split()
)
PARAMS = dict(
    version="alignment-1.0",
    page_tolerance=1,
    min_score=0.62,
    min_own_coverage=0.50,
    strong_score=0.78,
    strong_margin=0.10,
    weights=dict(own=0.55, context=0.10, page=0.35),
    no_historical_text_normalization=True,
)


def tokens(s):
    return {w for w in fold(s).split() if w not in STOP and len(w) > 2}


def coverage(wanted, found):
    if not wanted:
        return 0.0
    return sum(
        any(
            w == f
            or (len(w) >= 4 and f.startswith(w) and f[len(w) :] in {"ois", "ais", "s"})
            or difflib.SequenceMatcher(None, w, f).ratio() >= 0.84
            for f in found
        )
        for w in wanted
    ) / len(wanted)


def page_index(s):
    pp = []
    for offset, attrs in s.pages:
        n = attrs.get("n", "")
        pp.append(
            dict(
                offset=offset,
                page=int(n) if n.isdigit() else None,
                method="pb@n" if n.isdigit() else "unknown",
                image_id=attrs.get("id"),
            )
        )
    # Never confuse physical image index with printed pagination. Infer only a gap bounded by agreeing labels.
    for i, p in enumerate(pp):
        if p["page"] is not None:
            continue
        left = next((j for j in range(i - 1, -1, -1) if pp[j]["method"] == "pb@n"), None)
        right = next((j for j in range(i + 1, len(pp)) if pp[j]["method"] == "pb@n"), None)
        if (
            left is not None
            and right is not None
            and pp[right]["page"] - pp[left]["page"] == right - left
        ):
            p["page"] = pp[left]["page"] + i - left
            p["method"] = "interpolation_between_consistent_pb_labels"
    offsets = [p["offset"] for p in pp]

    def at(pos):
        i = bisect.bisect_right(offsets, pos) - 1
        return pp[i] if i >= 0 else dict(page=None, method="before_first_pb")

    return pp, at


def leaf_records(s):
    out = []
    for node in s.tree.xpath(
        '//text/body//*[starts-with(local-name(),"div")][p and not(*[starts-with(local-name(),"div")])]'
    ):
        a, b = s.span(node)
        title = " ".join(compact(h) for h in node.findall("head"))
        ps = node.findall("p")
        if not title or fold(title) in {"cahier", "cahiers"}:
            title += " " + " ".join(compact(p) for p in ps[:2] if len(compact(p)) < 900)
        ancestors = " ".join(
            compact(h) for h in node.xpath('ancestor::*[starts-with(local-name(),"div")]/head')
        )
        out.append(
            dict(
                xpath=s.tree.getpath(node),
                start=a,
                end=b,
                title=title.strip(),
                context=ancestors,
                node=node,
            )
        )
    return out


def candidates(record, s, leaves, at):
    a, b = record.get("page_start"), record.get("page_end")
    if a is None:
        return []
    found = []
    wanted = tokens(re.sub(r"\([^)]*\)", "", record["title"]))
    context_wanted = tokens(record["title"])
    for leaf in leaves:
        n = leaf["node"]
        ps = n.findall("p")
        heads = n.findall("head")
        display_start = s.span(heads[0] if heads else ps[0])[0]
        source_page = at(display_start)["page"]
        end_page = at(leaf["end"] - 1)["page"]
        if source_page is None or end_page is None or end_page < a - 1 or source_page > b + 1:
            continue
        options = [
            dict(
                anchor_xpath=leaf["xpath"],
                start=leaf["start"],
                display_start=display_start,
                title=leaf["title"],
                internal=False,
            )
        ]
        # Only paragraphs in the requested page window, not an extraction of all source documents.
        for i, p in enumerate(ps[2:], 2):
            text = compact(p)
            pa, pb = s.span(p)
            pg = at(pa)["page"]
            if pg is None or not a - 1 <= pg <= a + 1 or len(text) > 700:
                continue
            if not re.match(
                r"^(?:cahier|doleances|demandes|plaintes|remontr|instructions|pouvoirs|memoire|proces|chapitre|constitution|agriculture)",
                fold(text),
            ):
                continue
            title = (
                text
                + " "
                + " ".join(compact(q) for q in ps[i + 1 : i + 3] if len(compact(q)) < 700)
            )
            options.append(
                dict(
                    anchor_xpath=s.tree.getpath(p),
                    start=pa,
                    display_start=pa,
                    title=title,
                    internal=True,
                )
            )
        for c in options:
            pg = at(c["display_start"])["page"]
            if pg is None or abs(pg - a) > 1:
                continue
            own = coverage(wanted, tokens(c["title"]))
            context = coverage(context_wanted, tokens(c["title"] + " " + leaf["context"]))
            page_score = 1 if pg == a else 0.0
            score = 0.55 * own + 0.10 * context + 0.35 * page_score
            mt = tokens(record["title"])
            st = tokens(c["title"])
            if ("clerge" in mt and "noblesse" in st) or ("noblesse" in mt and "clerge" in st):
                score -= 0.4
            if c["internal"] and re.match(
                r"^(?:chapitre|constitution|agriculture)", fold(c["title"])
            ):
                score -= 0.15
            found.append(
                dict(
                    c,
                    volume=record["volume"],
                    xpath=leaf["xpath"],
                    context=leaf["context"],
                    page=pg,
                    page_method=at(c["display_start"])["method"],
                    own_coverage=own,
                    context_coverage=context,
                    score=round(score, 6),
                    leaf_end=leaf["end"],
                )
            )
    return sorted(found, key=lambda c: (-c["score"], not not c["internal"], c["start"]))


def boundary(record, c, s, leaves, at):
    leaf = next(leaf_record for leaf_record in leaves if leaf_record["xpath"] == c["xpath"])
    start, end = c["start"], leaf["end"]
    divisions = [c["xpath"]]
    n = leaf["node"]
    flags = []
    ps = n.findall("p")
    for i, p in enumerate(ps):
        pa, pb = s.span(p)
        if pa <= start:
            continue
        # A literal new CAHIER title with identity in following p; no semantic splitting.
        if (
            compact(p).strip() == "CAHIER"
            and i + 1 < len(ps)
            and re.search(
                r"paroisse|habitants|communaute|clerge|noblesse|tiers|ville",
                fold(compact(ps[i + 1])),
            )
        ):
            end = pa
            flags.append("next_literal_internal_cahier_title")
            break
    if not c["internal"] and end == leaf["end"]:
        for sib in n.itersiblings():
            if not isinstance(sib.tag, str) or not sib.tag.startswith("div"):
                continue
            path = s.tree.getpath(sib)
            leaf_record = next((x for x in leaves if x["xpath"] == path), None)
            if leaf_record is None:
                break
            title = fold(leaf_record["title"])
            sp = at(leaf_record["start"])["page"]
            if sp is None or sp > record["page_end"]:
                break
            if not re.match(
                r"^(?:chapitre|section|constitution|agriculture|demandes particulieres|travail|supplement)",
                title,
            ):
                break
            divisions.append(path)
            end = leaf_record["end"]
            flags.append("following_section_or_attached_piece_within_metadata_pages")
    last = at(end - 1)["page"]
    if last != record["page_end"]:
        flags.append("end_page_mismatch_requires_review")
    return dict(
        start=start,
        end=end,
        divisions=divisions,
        start_page=c["page"],
        end_page=last,
        flags=flags,
        status="proposed_not_verified",
        offsets="half-open decoded XML itertext Unicode positions",
    )


def align(record, s, leaves, at):
    cs = candidates(record, s, leaves, at)
    best = cs[0] if cs else None
    margin = (
        round(best["score"] - cs[1]["score"], 6)
        if len(cs) > 1
        else (best["score"] if best else None)
    )
    if (
        not best
        or best["score"] < PARAMS["min_score"]
        or best["own_coverage"] < PARAMS["min_own_coverage"]
    ):
        status = "not_found"
    elif best["score"] >= PARAMS["strong_score"] and margin >= PARAMS["strong_margin"]:
        status = "strong_proposal"
    else:
        status = "ambiguous_proposal"
    return dict(
        persee_id=record["id"],
        volume=record["volume"],
        title=record["title"],
        metadata_type=record.get("dc_type"),
        metadata_pages=[record.get("page_start"), record.get("page_end")],
        selection=record["selection"],
        status=status,
        margin=margin,
        candidates=cs[:5],
        boundary=boundary(record, best, s, leaves, at) if best and status != "not_found" else None,
        source=source_ref(s),
        confidence_is_not_probability=True,
        verification="not_reviewed",
    )


def main(development_only=False):
    ss = load_sources()
    indices = {v: (leaf_records(s), page_index(s)) for v, s in ss.items()}
    out = []
    for r in rows(HERE / "data/metadata.jsonl"):
        if development_only and r["selection"] != "development_control":
            continue
        leaves, (_, at) = indices[r["volume"]]
        out.append(align(r, ss[r["volume"]], leaves, at))
    jlines(
        HERE
        / (
            "data/development-predictions.jsonl"
            if development_only
            else "data/alignment-predictions.jsonl"
        ),
        out,
    )
    if not development_only:
        save(HERE / "data/page-index.json", {v: idx[1][0] for v, idx in indices.items()})
    print("aligned", len(out))


if __name__ == "__main__":
    import sys

    main("--development-only" in sys.argv)
