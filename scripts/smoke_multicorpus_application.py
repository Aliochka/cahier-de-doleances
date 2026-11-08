"""Read-only real local API checks. No publication or writes to either corpus."""

import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from sqlalchemy import text

    from documentary.integrate_local import verify_gdn
    from documentary.local_application import LocalApplicationDestination
    from documentary.storage import SCOPE

    config = json.loads((ROOT / "private/search/phase4/runtime.json").read_text())
    timings = []
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(path, *, preview=True, status=200, extra=None):
        headers = {"x-documentary-preview": config["preview_token"]} if preview else {}
        headers.update(extra or {})
        started = time.perf_counter()
        req = urllib.request.Request("http://127.0.0.1:8000" + path, headers=headers)
        try:
            with opener.open(req, timeout=20) as r:
                code = r.status
                value = json.load(r)
        except urllib.error.HTTPError as e:
            code = e.code
            value = json.load(e)
        timings.append(
            dict(path=path.split("?")[0], status=code, seconds=time.perf_counter() - started)
        )
        assert code == status, (path, code, value)
        return value

    def query(corpus, **kwargs):
        return "/api/v1/search?" + urllib.parse.urlencode(
            dict(q="Gabelle", corpus=corpus, **kwargs)
        )

    def key(i):
        return (
            ("1789", i["document_id"])
            if i["kind"] == "historical_document"
            else ("2019", i["answer_id"])
        )

    cohorts = {c: get(query(c)) for c in ["2019", "1789", "tous"]}
    assert all(i["kind"] == "questionnaire_answer" for i in cohorts["2019"]["items"])
    assert all(i["kind"] == "historical_document" for i in cohorts["1789"]["items"])
    first = cohorts["tous"]
    assert len({key(i) for i in first["items"]}) == len(first["items"])
    second = get(query("tous", cursor=first["next_cursor"]))
    assert not {key(i) for i in first["items"]} & {key(i) for i in second["items"]}
    repeated = get(query("tous", cursor=first["first_cursor"]))
    assert [key(i) for i in repeated["items"]] == [key(i) for i in first["items"]]
    get(query("2019", cursor=first["first_cursor"]), status=422)
    get(query("tous", cursor=first["first_cursor"]), preview=False, status=422)
    public = get(query("tous"), preview=False)
    assert all(i["kind"] == "questionnaire_answer" for i in public["items"])
    get("/api/v1/documentary/1789", preview=False, status=404)
    get(query("1789"), preview=False, status=422)
    catalogue = get("/api/v1/documentary/1789")
    assert catalogue["total"] == 1224
    next_page = get("/api/v1/documentary/1789?page=2")
    assert not {i["document_id"] for i in catalogue["items"]} & {
        i["document_id"] for i in next_page["items"]
    }
    d = catalogue["items"][0]
    base = f"/api/v1/documentary/1789/{d['release_id']}/documents/{urllib.parse.quote(d['document_id'], safe='')}"
    read = get(base)
    assert read["previous"] is None and read["next"] == catalogue["items"][1]["url"]
    full = "".join(b["text"] for b in read["blocks"])
    assert hashlib.sha256(full.encode()).hexdigest() == read["text_sha256"]
    get(base, preview=False, status=404)
    get(base, extra={"x-forwarded-for": "127.0.0.1"}, status=404)
    get(base.replace(d["release_id"], "old-release"), status=404)
    get(base + "?unit=unknown-unit", status=404)
    destination = LocalApplicationDestination(
        "postgresql+psycopg2:///cahier_rag?host=/var/run/postgresql"
    )
    with destination.transaction(readonly=True) as c:
        artois = c.execute(
            text("SELECT document_id FROM documentary.document WHERE document_id LIKE '%2_1_1578'")
        ).scalar_one()
        units = c.execute(
            text(
                "SELECT unit_id,searchable FROM documentary.search_unit WHERE document_id=:id ORDER BY ordinal"
            ),
            dict(id=artois),
        ).all()
        assert [u[1] for u in units] == [True, True, False, False]
        other = c.execute(
            text(
                "SELECT document_id FROM documentary.document WHERE NOT candidate ORDER BY edition_order LIMIT 1"
            )
        ).scalar_one()
        aunay = c.execute(
            text("SELECT document_id FROM documentary.document WHERE document_id LIKE '%2_1_1602'")
        ).scalar_one()
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM documentary.document WHERE readable OR searchable OR catalogue_visible"
                )
            ).scalar_one()
            == 0
        )
    get(
        f"/api/v1/documentary/1789/{SCOPE['release']}/documents/{urllib.parse.quote(other, safe='')}",
        status=404,
    )
    for doc, unit in [(artois, units[2][0]), (aunay, None)]:
        path = f"/api/v1/documentary/1789/{SCOPE['release']}/documents/{urllib.parse.quote(doc, safe='')}"
        if unit:
            path += "?" + urllib.parse.urlencode(dict(unit=unit))
        value = get(path)
        assert value["warnings"]
        if unit:
            mark = next(b for b in value["blocks"] if b["anchor"])
            assert mark["text"]
        else:
            assert (
                value["title"]
                == "Cahier des habitants d'Aunay-la-Côte, présenté au bailliage d'Avallon — 16 mars 1789"
            )
    qid = cohorts["2019"]["items"][0]["question"]["id"]
    question = get("/api/v1/search?" + urllib.parse.urlencode(dict(q="Gabelle", question_id=qid)))
    assert question["mode"] == "lexical" and all(
        i["question"]["id"] == qid for i in question["items"]
    )
    assert verify_gdn(destination, ROOT / "private/search/phase4/backup/manifest.json")
    destination.close()
    result = dict(
        api_checks=len(timings),
        timings=timings,
        publication_authorized=False,
        text_integrity=True,
        editorial_exclusions=True,
        aunay_title=True,
        unicode_anchors=True,
        pagination=True,
        corpus_binding=True,
        preview_required=True,
        question_h1_preserved=True,
        gdn_unchanged=True,
    )
    (ROOT / "private/search/phase4/api-tests.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "timings"}))


if __name__ == "__main__":
    main()
