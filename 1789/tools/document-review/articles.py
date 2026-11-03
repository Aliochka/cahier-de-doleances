"""Article decisions over immutable source ranges; independent from the parent journal."""

import copy
import gzip
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from reviewlib import HERE, PRIVATE, Conflict, Store, rows, sha

VERSION = "article-review-1.0"
INPUT = HERE.parents[1] / "data/article-corpus"
TYPES = {"article", "section", "technical_passage", "claim_passage", "paratext"}
HUMAN = {"human_validated", "human_corrected"}


class Journal:
    # Exactly the same lock/fsync/hash-chain convention as the Cahiers journal.
    history = Store.history
    locked_journal = Store.locked_journal

    def __init__(self, path):
        self.journal = Path(path)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def subtract(spans, exclusions):
    result = []
    for start, end in spans:
        cursor = start
        for a, z in sorted(exclusions):
            if z <= cursor or a >= end:
                continue
            if cursor < a:
                result.append([cursor, min(a, end)])
            cursor = max(cursor, z)
        if cursor < end:
            result.append([cursor, end])
    return result


def intersects(left, right):
    return any(a < z and x < b for a, b in left for x, z in right)


class Articles:
    def __init__(self, parent_store, journal=None, directory=INPUT, override_directory=None):
        self.store = parent_store
        self.log = Journal(journal or PRIVATE / "article-decisions.jsonl")
        if self.log.journal.resolve() == self.store.journal.resolve():
            raise ValueError("Article and Cahiers journals must be distinct")
        self.directory = Path(directory)
        self.override_directory = (
            Path(override_directory) if override_directory else PRIVATE / "corpus-overrides"
        )
        self._fusion_cache = None
        self._thematic_cache = None
        self._quality_cache = None
        self._quality_summary = None
        self._finalization_changes = None
        self._stat_fingerprint = None
        self.fingerprint = None
        self.refresh()

    @staticmethod
    def record_from_unit(p, u):
        return dict(
            id=u["id"],
            parent_id=p["id"],
            parent_extent_id=p["extent_id"],
            type=u["type"],
            number=u["historical_number"],
            label=u["label_exact"],
            number_origin="source_recognition",
            source_status=u["status"],
            review_status="codex_examined"
            if u["status"] == "A"
            else "automatic_proposal"
            if u["status"] == "B"
            else "technical_unclassified",
            spans=u["text_spans"],
            origin_ids=u.get("origin_ids", [u["id"]]),
            section_id=u["section_id"],
            last_event_id=None,
        )

    def refresh(self):
        paths = [
            self.directory / name
            for name in [
                "parents.jsonl.gz",
                "units-A.jsonl.gz",
                "units-B.jsonl.gz",
                "units-C.jsonl.gz",
            ]
        ]
        override_log = self.override_directory / "rebuilds.jsonl"
        use_overrides = (self.directory / "complete.json").exists()
        watch = paths + ([override_log] if use_overrides and override_log.exists() else [])
        signature = [(str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in watch]
        if signature == self._stat_fingerprint:
            return
        fingerprint = sha(canonical({str(p): sha(p.read_bytes()) for p in watch}))
        if fingerprint == self.fingerprint:
            return
        parents = rows(paths[0])
        self.parents = {p["id"]: p for p in parents}
        self.base = {p["id"]: {} for p in parents}
        for path in paths[1:]:
            for u in rows(path):
                p = self.parents[u["parent_id"]]
                record = self.record_from_unit(p, u)
                if record["id"] in self.base[p["id"]]:
                    raise ValueError("Duplicate baseline unit")
                self.base[p["id"]][u["id"]] = record
        if use_overrides:
            from collection import overrides

            for amendment in overrides(self.directory, self.override_directory):
                p = amendment["parent"]
                self.parents[p["id"]] = p
                self.base[p["id"]] = {
                    u["id"]: self.record_from_unit(p, u) for u in amendment["units"]
                }
        for p in self.parents.values():
            source = self.store.sources[p["volume"]]
            if (
                source.sha256 != p["source"]["source_sha256"]
                or source.text[p["start"] : p["end"]] != p["full_text"]
            ):
                raise ValueError("Parent/source mismatch")
            self.check(p, list(self.base[p["id"]].values()))
        self.fingerprint = fingerprint
        self._stat_fingerprint = signature

    def parent_version(self, p):
        r = self.store.by_id[p["id"]]
        state = self.store.state(r, getattr(self, "_listing_parent_events", None))
        span = state["selected"] or {}
        compatible = (
            not state["stale"] and span.get("start") == p["start"] and span.get("end") == p["end"]
        )
        ready = compatible and state["status"] == "human_validated"
        reviewable = compatible and state["status"] in {
            "proposed",
            "codex_reviewed",
            "human_validated",
        }
        return dict(
            extent_id=p["extent_id"],
            source_sha256=p["source"]["source_sha256"],
            start=p["start"],
            end=p["end"],
            current_start=span.get("start"),
            current_end=span.get("end"),
            current_status=state["status"],
            compatible=compatible,
            ready=ready,
            reviewable=reviewable,
            current_parent_event=(state["event"] or {}).get("id"),
        )

    def version(self, p):
        return dict(
            corpus_fingerprint=self.fingerprint, parent=self.parent_version(p), method=VERSION
        )

    def state(self, key, events=None):
        self.refresh()
        p = self.parents[key]
        records = copy.deepcopy(self.base[key])
        history = [
            e for e in (self.log.history() if events is None else events) if e["document_id"] == key
        ]
        stale = []
        head = history[-1]["id"] if history else None
        for event in history:
            if (
                event["parent_extent_id"] != p["extent_id"]
                or event["source_sha256"] != p["source"]["source_sha256"]
            ):
                stale.append(event["id"])
                continue
            for old in event["before"]:
                records.pop(old["id"], None)
            for new in event["after"]:
                records[new["id"]] = copy.deepcopy(new)
        return p, records, history, head, stale

    def check(self, p, records):
        ids = [r["id"] for r in records]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate units")
        coverage = []
        for r in records:
            if (
                r["parent_id"] != p["id"]
                or r["parent_extent_id"] != p["extent_id"]
                or r["type"] not in TYPES
            ):
                raise ValueError("Unit/parent/type mismatch")
            if not r["spans"]:
                raise ValueError("Empty unit")
            last = -1
            for a, z in r["spans"]:
                if (
                    isinstance(a, bool)
                    or isinstance(z, bool)
                    or not isinstance(a, int)
                    or not isinstance(z, int)
                    or not p["start"] <= a < z <= p["end"]
                    or a < last
                ):
                    raise ValueError("Invalid source ranges")
                last = z
                coverage.append((a, z, r["id"]))
            if r["number"] is not None and (
                not isinstance(r["number"], str) or len(r["number"]) > 80
            ):
                raise ValueError("Invalid historical number")
            if r["type"] != "article" and r["number"] is not None:
                raise ValueError("Only historical articles have a historical number")
        cursor = p["start"]
        for a, z, _ in sorted(coverage):
            if a != cursor:
                raise ValueError("Uncovered or overlapping source text")
            cursor = z
        if cursor != p["end"]:
            raise ValueError("Uncovered end of parent")

    def text(self, p, record):
        source = self.store.sources[p["volume"]]
        return "".join(source.text[a:z] for a, z in record["spans"])

    def anomalies(self, p, records, stale_events=None):
        flags = {r["id"]: [] for r in records}
        articles = sorted(
            [r for r in records if r["type"] == "article"], key=lambda r: r["spans"][0][0]
        )
        seen = set()
        previous = {}
        for r in articles:
            key = (r.get("section_id"), r["number"])
            if r["number"] is not None:
                if key in seen:
                    flags[r["id"]].append(
                        "Numéro répété dans la même section : vérifier la reprise de numérotation."
                    )
                seen.add(key)
                m = re.fullmatch(r"(\d+)(?:er|re|e)?", r["number"])
                if m:
                    n = int(m[1])
                    prev = previous.get(r.get("section_id"))
                    if prev is not None and n != prev + 1:
                        flags[r["id"]].append(
                            "Suite de numéros irrégulière ; aucune renumérotation automatique."
                        )
                    previous[r.get("section_id")] = n
            elif (self.thematic_context(r) or {}).get("unit_form") != "unnumbered_thematic_claim":
                flags[r["id"]].append("Numéro non reconnu ; vérifier le repère original.")
            if sum(z - a for a, z in r["spans"]) > 12000:
                flags[r["id"]].append("unusually_long_article_over_12000_chars")
            if not self.text(p, r).strip():
                flags[r["id"]].append("Texte vide.")
        # Optional proposals flag unreviewed fusions but never invalidate human decisions.
        from segmentation_comparison import comparison

        proposals = comparison(p)
        if proposals and proposals.get("available"):
            for marker in proposals["markers"]:
                point = marker["start"]
                if any(abs(r["spans"][0][0] - point) <= 3 for r in articles):
                    continue  # Already separated, including a human correction.
                for r in articles:
                    if r["review_status"] not in HUMAN and any(
                        a < point < z for a, z in r["spans"]
                    ):
                        flags[r["id"]].append(
                            f"Fusion potentielle : repère {marker['label']} à la position {point}. "
                            "Examiner la comparaison de segmentation avant validation."
                        )
        for r in records:
            if r["review_status"] == "uncertain":
                flags[r["id"]].append("Délimitation ou qualification laissée incertaine.")
            if stale_events and r["last_event_id"] is None:
                flags[r["id"]].append(
                    "Anciennes décisions liées à une autre version du cahier : réexamen requis."
                )
        for marker in p.get("segmentation_alerts", []):
            for r in articles:
                if r["review_status"] not in HUMAN and any(
                    a < marker["start"] < z for a, z in r["spans"]
                ):
                    flags[r["id"]].append(
                        "Fusion potentielle signalée par le segmenteur : " + marker["raw_label"]
                    )
        return flags

    def thematic_context(self, record):
        if self._thematic_cache is None:
            path = self.directory / "thematic-regions.jsonl.gz"
            self._thematic_cache = {}
            if path.exists():
                for h in rows(path):
                    self._thematic_cache.setdefault(h["parent_id"], []).append(h)
        from thematic import context

        hypotheses = [
            h
            for h in self._thematic_cache.get(record["parent_id"], [])
            if h.get("parent_extent_id") == record["parent_extent_id"]
        ]
        return context(record, hypotheses)

    def quality_summary(self):
        if self._quality_summary is None:
            path = self.directory / "article-quality-summary.json"
            self._quality_summary = json.loads(path.read_text()) if path.exists() else {}
        return self._quality_summary

    def unit_quality(self, record):
        if self._quality_cache is None:
            path = self.directory / "unit-quality.jsonl.gz"
            self._quality_cache = {r["unit_id"]: r for r in rows(path)} if path.exists() else {}
        quality = self._quality_cache.get(record["id"])
        return (
            dict(
                quality,
                analysis_may_be_stale=quality.get("last_event_id") != record.get("last_event_id"),
            )
            if quality
            else None
        )

    def finalization_changes(self, p):
        if self._finalization_changes is None:
            path = self.directory / "article-changes.jsonl.gz"
            self._finalization_changes = {}
            if path.exists():
                for r in rows(path):
                    self._finalization_changes.setdefault(r["parent_id"], []).append(r)
        source = self.store.sources[p["volume"]]
        return [
            dict(r, before_text="".join(source.text[a:z] for a, z in r["old_spans"]))
            for r in self._finalization_changes.get(p["id"], [])
        ]

    def automatic_whitespace(self, p, record):
        """Only unclassified C; preserve explicit human classifications and exact ranges."""
        return (
            record["type"] == "technical_passage"
            and record["review_status"] == "technical_unclassified"
            and self.text(p, record).isspace()
        )

    def present(self, p, records, stale_events=None):
        ordered = sorted(records, key=lambda r: (r["spans"][0][0], r["spans"][-1][1], r["id"]))
        flags = self.anomalies(p, ordered, stale_events)
        version = self.parent_version(p)
        source = self.store.sources[p["volume"]]
        output = []
        for i, r in enumerate(ordered):
            a, z = r["spans"][0][0], r["spans"][-1][1]
            pages = source.pages_for(a, z)
            old_validation = r["review_status"] in HUMAN
            invalidated = not version["reviewable"] or bool(
                stale_events and r["last_event_id"] is None
            )
            status = "review_required" if invalidated and old_validation else r["review_status"]
            eligible = (
                version["ready"]
                and not invalidated
                and status not in {"uncertain", "review_required"}
                and r["type"] in {"article", "claim_passage", "section"}
            )
            text = self.text(p, r)
            whitespace = self.automatic_whitespace(p, r)
            if whitespace:
                status = "automatic_technical_paratext"
                eligible = False
            blocks = [
                dict(id=b["id"], xpath=b["xpath"], start=max(a, b["start"]), end=min(z, b["end"]))
                for b in self.store.selected_blocks(p["volume"], a, z)
                if b["tag"] != "pb"
            ]
            image = None
            if pages and pages[0].get("id"):
                image = f"https://stacks.stanford.edu/image/iiif/{source.path.stem}%2F{pages[0]['id']}/full/1200,/0/default.jpg"
            output.append(
                dict(
                    r,
                    type="paratext" if whitespace else r["type"],
                    original_type=r["type"],
                    automatic_classification=(
                        dict(
                            version="unicode-whitespace-1",
                            origin="deterministic_rule",
                            reason="exclusively_Unicode_whitespace",
                            original_type="technical_passage",
                        )
                        if whitespace
                        else None
                    ),
                    requires_human_classification=r["type"] == "technical_passage"
                    and not whitespace,
                    text=text,
                    text_sha256=sha(text),
                    start=a,
                    end=z,
                    parent_start=a - p["start"],
                    parent_end=z - p["start"],
                    parent_spans=[[x - p["start"], y - p["start"]] for x, y in r["spans"]],
                    order=i + 1,
                    pages=pages,
                    previous_unit_id=ordered[i - 1]["id"] if i else None,
                    next_unit_id=ordered[i + 1]["id"] if i + 1 < len(ordered) else None,
                    order_status="source_order_not_certified_historical_succession",
                    anomalies=flags[r["id"]],
                    quality=self.unit_quality(r),
                    thematic_context=self.thematic_context(r),
                    effective_section_id=(self.thematic_context(r) or {}).get("section_id")
                    or r["section_id"],
                    validation_status=status,
                    human_validated=old_validation and not invalidated,
                    indexing_eligible=eligible,
                    publication_ready=eligible and old_validation and not flags[r["id"]],
                    parent_version=version,
                    source=p["source"],
                    xml_blocks=blocks,
                    source_page_url=image,
                    section=next(
                        (
                            s["heading"]
                            for s in p.get("sections", [])
                            if s["id"] == r.get("section_id")
                        ),
                        None,
                    ),
                    original_proposals=[
                        self.base[p["id"]][key]
                        for key in r["origin_ids"]
                        if key in self.base[p["id"]]
                    ],
                )
            )
        return output

    def listing(self):
        self.refresh()
        events = self.log.history()
        self._listing_parent_events = self.store.latest()
        result = []
        for key in self.parents:
            p, records, history, head, stale = self.state(key, events)
            actual = list(records.values())
            version = self.parent_version(p)
            result.append(
                dict(
                    id=key,
                    title=p["metadata"]["title"],
                    volume=p["volume"],
                    persee_id=p["persee_id"],
                    parent_ready=version["ready"],
                    boundary_class="human_validated"
                    if version["ready"]
                    else p.get("boundary_class", "uncertain"),
                    document_kind=p.get("document_kind", "cahier_autonome_probable"),
                    documentary_anomalies=p.get("anomalies", []),
                    article_quality=self.quality_summary().get("by_parent", {}).get(key, {}),
                    automatic_technical_paratext=sum(
                        self.automatic_whitespace(p, r) for r in actual
                    ),
                    technical_passages_to_classify=sum(
                        r["type"] == "technical_passage" and not self.automatic_whitespace(p, r)
                        for r in actual
                    ),
                    articles=sum(r["type"] == "article" for r in actual),
                    human_reviewed=sum(
                        r["review_status"] in HUMAN and version["reviewable"] and not stale
                        for r in actual
                    ),
                    proposed_articles=sum(
                        r["type"] == "article" and r["source_status"] == "B" for r in actual
                    ),
                    longest_technical_passage=max(
                        (
                            sum(z - a for a, z in r["spans"])
                            for r in actual
                            if r["type"] == "technical_passage"
                            and not self.automatic_whitespace(p, r)
                        ),
                        default=0,
                    ),
                    uncertain=sum(r["review_status"] == "uncertain" for r in actual),
                    stale_decisions=len(stale),
                    units=len(actual),
                )
            )
        self._listing_parent_events = None
        return result

    def workbench_progress(self, windows):
        """Progress of each frozen source window, never of the whole parent."""
        events = self.log.history()
        states = {}
        result = {}
        for window in windows:
            key = window["parent_id"]
            if key not in self.parents:
                result[window["id"]] = dict(status="review_required", reviewed=0, remaining=0)
                continue
            if key not in states:
                states[key] = self.state(key, events)
            p, records, _, _, stale = states[key]
            original = self.base[key].get(window["unit_id"])
            spans = original["spans"] if original else [[window["start"], window["end"]]]
            own = [r for r in records.values() if intersects(r["spans"], spans)]
            relevant = [r for r in own if not self.automatic_whitespace(p, r)]
            reviewed = sum(r["review_status"] in HUMAN for r in relevant)
            uncertain = sum(r["review_status"] == "uncertain" for r in relevant)
            compatible = (
                self.parent_version(p)["reviewable"]
                and not stale
                and all(p["start"] <= a < z <= p["end"] for a, z in spans)
            )
            status = (
                "review_required"
                if not compatible or not own
                else "automatic"
                if not relevant
                else "uncertain"
                if uncertain
                else "completed"
                if reviewed == len(relevant)
                else "in_progress"
                if reviewed or any(r.get("last_event_id") for r in relevant)
                else "pending"
            )
            result[window["id"]] = dict(
                status=status,
                reviewed=reviewed,
                remaining=len(relevant) - reviewed,
                uncertain=uncertain,
                automatic_whitespace=len(own) - len(relevant),
                unit_ids=[r["id"] for r in (relevant or own)],
            )
        return result

    def fusion_report(self, parent):
        if self._fusion_cache is None:
            self._fusion_cache = {"changes": {}, "proposals": {}}
            for field, name in [
                ("changes", "fusion-changes.jsonl.gz"),
                ("proposals", "fusion-candidates.jsonl.gz"),
            ]:
                path = self.directory / name
                if path.exists():
                    for item in rows(path):
                        self._fusion_cache[field].setdefault(item["parent_id"], []).append(item)
        source = self.store.sources[parent["volume"]]
        changes = [
            dict(c, before_text="".join(source.text[a:z] for a, z in c["old_spans"]))
            for c in self._fusion_cache["changes"].get(parent["id"], [])
        ]
        credible = [
            h
            for h in self._fusion_cache["proposals"].get(parent["id"], [])
            if h["application"] != "applied_automatic_proposal"
            and "explicit_historical_request_formula" in h["evidence"]
            and "title_words_in_development_and_new_relative_to_previous_paragraphs"
            in h["evidence"]
        ]
        return dict(
            changes=changes,
            proposals=credible[:20],
            proposal_count=len(credible),
            warning="Propositions figées de cette génération. Les décisions humaines actuelles restent prioritaires ; aucune suggestion ne les remplace.",
        )

    def document(self, key):
        from segmentation_comparison import comparison

        p, records, history, head, stale = self.state(key)
        return dict(
            segmentation_comparison=comparison(p),
            parent={
                "boundary_class": "human_validated"
                if self.parent_version(p)["ready"]
                else p.get("boundary_class", "uncertain"),
                **{
                    k: p[k] for k in ["document_kind", "anomalies", "segmentation_policy"] if k in p
                },
                **{
                    k: p[k]
                    for k in [
                        "id",
                        "extent_id",
                        "volume",
                        "metadata",
                        "source",
                        "start",
                        "end",
                        "full_text",
                        "sections",
                    ]
                },
            },
            version=self.version(p),
            previous_event_id=head,
            units=self.present(p, list(records.values()), stale),
            finalization_changes=self.finalization_changes(p),
            fusion_report=self.fusion_report(p),
            history=[
                {
                    k: e[k]
                    for k in ["id", "date", "action", "note", "affected_ids", "parent_extent_id"]
                }
                for e in history
            ],
            stale_events=stale,
            warning=None
            if self.parent_version(p)["ready"]
            else (
                "Frontières du cahier encore proposées : vous pouvez examiner et classer ses unités sur ce périmètre. Ces décisions ne valident pas le cahier ; ses unités restent exclues de la publication et de l’export éligible tant que le parent n’est pas validé."
                if self.parent_version(p)["reviewable"]
                else "Périmètre du cahier incompatible, incertain ou bloqué : vérifiez ses frontières et reconstruisez le document si nécessaire avant de modifier ses unités."
            ),
        )

    def _new(self, p, kind, spans, origins, number=None, section=None):
        identifier = "ap1789-reviewed-unit-1:" + sha(canonical([p["extent_id"], kind, spans]))[:28]
        return dict(
            id=identifier,
            parent_id=p["id"],
            parent_extent_id=p["extent_id"],
            type=kind,
            number=number,
            label=None,
            number_origin="human_attribution" if number is not None else "none",
            source_status="C" if kind == "technical_passage" else "human_created",
            review_status="human_corrected",
            spans=spans,
            origin_ids=sorted(set(origins)),
            section_id=section,
            last_event_id=None,
        )

    def _range(self, p, payload):
        start, end = payload.get("start"), payload.get("end")
        if (
            type(start) is not int
            or type(end) is not int
            or not p["start"] <= start < end <= p["end"]
        ):
            raise ValueError("Sélectionnez une plage exacte dans le texte du cahier.")
        return start, end

    def _content_spans(self, p, start, end, kind):
        # Explicit TEI notes stay in the parent, never rewritten into a citizen claim.
        excluded = (
            [
                (n["start"], n["end"])
                for n in p.get("annotations", [])
                if n.get("role") == "XML_editorial_note"
            ]
            if kind in {"article", "claim_passage"}
            else []
        )
        spans = subtract([[start, end]], excluded)
        if not "".join(self.store.sources[p["volume"]].text[a:z] for a, z in spans).strip():
            raise ValueError(
                "La sélection ne contient pas de texte exploitable hors note éditoriale."
            )
        return spans

    def plan(self, payload, events=None):
        p, records, history, head, stale = self.state(payload["document_id"], events)
        if payload.get("version") != self.version(p) or payload.get("previous_event_id") != head:
            raise Conflict("Le cahier ou ses décisions ont changé. Rechargez avant de poursuivre.")
        action = payload["action"]
        ids = payload.get("unit_ids", [])
        if not isinstance(ids, list) or len(ids) != len(set(ids)) or len(ids) > 100:
            raise ValueError("Sélection explicite et unique, limitée à 100 unités.")
        if any(i not in records for i in ids):
            raise Conflict("Une unité a changé ou a été remplacée. Rechargez le cahier.")
        selected = [copy.deepcopy(records[i]) for i in ids]
        before = []
        after = []
        if action not in {"uncertain", "undo"} and not self.parent_version(p)["reviewable"]:
            raise Conflict(
                "Le périmètre du cahier est incompatible, incertain ou bloqué. Vérifiez ses frontières et reconstruisez le document avant cette opération."
            )
        flags = self.anomalies(p, list(records.values()), stale)
        if action == "validate":
            if not selected:
                raise ValueError("Sélectionnez les unités effectivement examinées.")
            if any(r["type"] == "technical_passage" for r in selected):
                raise ValueError(
                    "Classez les passages C avant de les valider ; ils ne sont pas des articles."
                )
            warnings = [m for r in selected for m in flags[r["id"]]]
            if warnings and (len(selected) > 1 or payload.get("acknowledge_anomalies") is not True):
                raise ValueError(
                    "Une unité comporte une anomalie ou une incertitude : examinez-la individuellement."
                )
            before = selected
            after = copy.deepcopy(selected)
            for r in after:
                r["review_status"] = "human_validated"
        elif action == "uncertain":
            if len(selected) != 1:
                raise ValueError("Choisissez une unité à laisser incertaine.")
            before = selected
            after = copy.deepcopy(selected)
            after[0]["review_status"] = "uncertain"
        elif action == "number":
            if len(selected) != 1 or selected[0]["type"] != "article":
                raise ValueError("Choisissez un article historique.")
            number = payload.get("number") or None
            if number is not None and (not isinstance(number, str) or len(number) > 80):
                raise ValueError("Numéro trop long.")
            before = selected
            after = copy.deepcopy(selected)
            after[0].update(
                number=number, number_origin="human_attribution", review_status="human_corrected"
            )
        elif action == "classify" and payload.get("type") != "article":
            if len(selected) != 1 or payload.get("type") not in {
                "paratext",
                "claim_passage",
                "section",
                "technical_passage",
            }:
                raise ValueError(
                    "Classement : paratexte, passage revendicatif, section ou incertain."
                )
            old = selected[0]
            kind = payload["type"]
            before = selected
            new = self._new(p, kind, old["spans"], old["origin_ids"], section=old["section_id"])
            new["source_status"] = old["source_status"]
            if kind == old["type"]:
                new["id"] = old["id"]
            if kind == "technical_passage":
                new["review_status"] = "uncertain"
            after = [new]
        elif action in {"correct", "merge", "missing", "split", "classify"}:
            if action == "split":
                if len(selected) != 1:
                    raise ValueError("Sélectionnez une seule unité à séparer.")
                old = selected[0]
                point = payload.get("point")
                if type(point) is not int or not old["spans"][0][0] < point < old["spans"][-1][1]:
                    raise ValueError("Choisissez la séparation à l’intérieur du texte.")
                before = selected
                for a, z, number in [
                    (old["spans"][0][0], point, payload.get("number")),
                    (point, old["spans"][-1][1], payload.get("second_number")),
                ]:
                    spans = []
                    for x, y in old["spans"]:
                        if max(x, a) < min(y, z):
                            spans.append([max(x, a), min(y, z)])
                    if not spans or not self.text(p, dict(spans=spans)).strip():
                        raise ValueError("Les deux fragments doivent contenir du texte.")
                    after.append(
                        self._new(
                            p,
                            old["type"],
                            spans,
                            old["origin_ids"],
                            number if old["type"] == "article" else None,
                            old["section_id"],
                        )
                    )
            else:
                if action in {"correct", "classify"} and len(selected) != 1:
                    raise ValueError("Sélectionnez une unité à corriger.")
                if action == "missing" and selected:
                    raise ValueError(
                        "Un ajout utilise la sélection de texte, sans article existant sélectionné."
                    )
                if action == "merge" and len(selected) < 2:
                    raise ValueError("Sélectionnez au moins deux fragments du même article.")
                kind = payload.get("type", selected[0]["type"] if selected else "article")
                if kind not in TYPES:
                    raise ValueError("Type documentaire inconnu.")
                if action == "merge":
                    start = min(r["spans"][0][0] for r in selected)
                    end = max(r["spans"][-1][1] for r in selected)
                elif action == "classify" and "start" not in payload and "end" not in payload:
                    start, end = selected[0]["spans"][0][0], selected[0]["spans"][-1][1]
                else:
                    start, end = self._range(p, payload)
                section = next(
                    (s["id"] for s in reversed(p.get("sections", [])) if s["start"] <= start), None
                )
                new = self._new(
                    p,
                    kind,
                    self._content_spans(p, start, end, kind),
                    [i for r in selected for i in r["origin_ids"]],
                    payload.get("number") if kind == "article" else None,
                    section,
                )
                # Edits cannot silently eat another article or an already classified/validated passage.
                affected = set(ids)
                for r in records.values():
                    if r["id"] in affected or not intersects(r["spans"], new["spans"]):
                        continue
                    if (
                        r["type"] != "technical_passage"
                        or r["review_status"] != "technical_unclassified"
                    ):
                        raise ValueError(
                            "La sélection recouvre une autre unité : sélectionnez explicitement les fragments à fusionner, ou ajustez les limites."
                        )
                    affected.add(r["id"])
                before = [copy.deepcopy(records[i]) for i in sorted(affected)]
                new["origin_ids"] = sorted(set(i for r in before for i in r["origin_ids"]))
                if (
                    selected
                    and len(selected) == 1
                    and selected[0]["type"] == kind
                    and selected[0]["spans"] == new["spans"]
                ):
                    new["id"] = selected[0]["id"]
                    new["source_status"] = selected[0]["source_status"]
                after = [new]
                # Every vacated or untouched note/space is retained as a technical source range.
                remaining = subtract([span for r in before for span in r["spans"]], new["spans"])
                for span in remaining:
                    left = self._new(
                        p, "technical_passage", [span], new["origin_ids"], section=section
                    )
                    left["review_status"] = "technical_unclassified"
                    after.append(left)
        elif action == "undo":
            if not history:
                raise ValueError("Aucune décision à annuler.")
            event = history[-1]
            if event["parent_extent_id"] != p["extent_id"]:
                raise Conflict("Cette décision concerne une autre version du cahier.")
            before = [copy.deepcopy(records[r["id"]]) for r in event["after"] if r["id"] in records]
            if len(before) != len(event["after"]):
                raise Conflict("La décision ne peut plus être inversée directement.")
            after = copy.deepcopy(event["before"])
        else:
            raise ValueError("Opération inconnue.")
        result = {i: copy.deepcopy(r) for i, r in records.items()}
        for r in before:
            result.pop(r["id"], None)
        for r in after:
            if r["id"] in result:
                raise ValueError("Cette correction créerait une unité dupliquée.")
            result[r["id"]] = r
        self.check(p, list(result.values()))
        digest = sha(
            canonical(
                dict(action=action, before=before, after=after, version=self.version(p), head=head)
            )
        )
        return p, before, after, digest

    def preview(self, payload):
        p, before, after, digest = self.plan(payload)
        return dict(
            digest=digest,
            removed_ids=[r["id"] for r in before],
            after=self.present(p, after),
            message="Les textes proviennent exclusivement des positions sélectionnées. Les fragments restants et notes sont conservés.",
        )

    def save(self, payload):
        if payload.get("confirmation") is not True:
            raise ValueError("Confirmez explicitement les unités examinées.")
        reviewer = payload.get("reviewer")
        note = payload.get("note", "")
        if (
            not isinstance(reviewer, str)
            or not reviewer.strip()
            or len(reviewer) > 160
            or not isinstance(note, str)
            or len(note) > 8000
        ):
            raise ValueError("Nom/pseudonyme requis ; remarque limitée à 8 000 caractères.")
        with self.log.locked_journal() as f:
            events = self.log.history()
            p, before, after, digest = self.plan(payload, events)
            if (
                payload["action"] not in {"validate", "uncertain", "undo"}
                and payload.get("preview_digest") != digest
            ):
                raise Conflict("Prévisualisez la correction exacte avant de l’enregistrer.")
            event_id = str(uuid.uuid4())
            # Undo restores earlier human states and their own evidence, not a new validation.
            if payload["action"] != "undo":
                for r in after:
                    r["last_event_id"] = event_id
            event = dict(
                id=event_id,
                document_id=p["id"],
                parent_extent_id=p["extent_id"],
                source_sha256=p["source"]["source_sha256"],
                version=self.version(p),
                action=payload["action"],
                date=datetime.now(timezone.utc).isoformat(),
                reviewer=reviewer.strip(),
                actor_type="human",
                note=note,
                confirmation=True,
                previous_event_id=payload.get("previous_event_id"),
                previous_hash=events[-1]["event_hash"] if events else None,
                affected_ids=[r["id"] for r in before],
                before=before,
                after=after,
                preview_digest=digest,
                method=VERSION,
            )
            event["event_hash"] = sha(canonical(event))
            f.seek(0, os.SEEK_END)
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return dict(id=event_id, action=event["action"], affected=len(before), created=len(after))

    def export(self):
        self.refresh()
        events = self.log.history()
        units = []
        invalidated = []
        for key in self.parents:
            p, records, _, _, stale = self.state(key, events)
            self.check(p, list(records.values()))
            rendered = self.present(p, list(records.values()), stale)
            units.extend(rendered)
            if stale or not self.parent_version(p)["ready"]:
                invalidated.append(
                    dict(document_id=key, stale_event_ids=stale, parent=self.parent_version(p))
                )
        if len({r["id"] for r in units}) != len(units):
            raise ValueError("Duplicate export IDs")
        from collections import Counter

        summary = dict(
            parents=len(self.parents),
            units=len(units),
            by_type=dict(Counter(r["type"] for r in units)),
            article_source_status=dict(
                Counter(r["source_status"] for r in units if r["type"] == "article")
            ),
            article_validation_status=dict(
                Counter(r["validation_status"] for r in units if r["type"] == "article")
            ),
            by_source_status=dict(Counter(r["source_status"] for r in units)),
            by_validation=dict(Counter(r["validation_status"] for r in units)),
            automatic_technical_paratext=sum(bool(r["automatic_classification"]) for r in units),
            technical_passages_to_classify=sum(r["requires_human_classification"] for r in units),
            human_validated_units=sum(r["human_validated"] for r in units),
            indexing_eligible=sum(r["indexing_eligible"] for r in units),
            publication_ready=sum(r["publication_ready"] for r in units),
            invalidated_parents=len(invalidated),
            article_journal_events=len(events),
            article_journal_sha256=sha(
                self.log.journal.read_bytes() if self.log.journal.exists() else b""
            ),
            corpus_fingerprint=self.fingerprint,
            method=VERSION,
            no_embeddings=True,
        )
        return units, summary, invalidated

    def write_export(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        units, summary, invalidated = self.export()
        for name, data in [("units.jsonl.gz", units), ("invalidated.jsonl.gz", invalidated)]:
            content = "".join(canonical(r) + "\n" for r in data).encode()
            (directory / name).write_bytes(gzip.compress(content, mtime=0))
        (directory / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
        )
        (directory / "manifest.json").write_text(
            json.dumps(
                {
                    p.name: sha(p.read_bytes())
                    for p in sorted(directory.iterdir())
                    if p.name in {"units.jsonl.gz", "invalidated.jsonl.gz", "summary.json"}
                },
                indent=2,
            )
            + "\n"
        )
        return summary
