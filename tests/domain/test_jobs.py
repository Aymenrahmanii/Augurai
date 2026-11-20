from augurai.domain.jobs import merge_snapshots, snapshot
from augurai.models import JobSnapshot, RawItem


def job(
    text: str, market: str = "global", source: str = "jobs-hn", title: str = "Engineer"
) -> RawItem:
    return RawItem(
        id=text[:8] + title,
        source=source,
        kind="job",
        title=title,
        url="https://x/" + text[:8],
        extra={"market": market, "text": text},
    )


def test_keyword_word_boundary():
    snaps = snapshot([job("We use RAG and LLMs")], "2026-11", ["RAG", "LLM"])
    assert snaps[0].keyword_counts == {"RAG": 1, "LLM": 0}  # "LLMs" is not "LLM"


def test_keyword_counted_once_per_posting_and_case_insensitive():
    snaps = snapshot([job("rag RAG Rag"), job("no match")], "2026-11", ["RAG"])
    assert snaps[0].keyword_counts == {"RAG": 1} and snaps[0].total_posts == 2


def test_one_snapshot_per_market_and_source():
    items = [
        job("a", "global", "jobs-hn"),
        job("b", "global", "jobs-remoteok"),
        job("c", "fr", "jobs-adzuna"),
    ]
    snaps = snapshot(items, "2026-11", ["RAG"])
    assert {s.id for s in snaps} == {
        "global-jobs-hn-2026-11",
        "global-jobs-remoteok-2026-11",
        "fr-jobs-adzuna-2026-11",
    }


def test_aggregate_items_supply_counts_and_total():
    agg = [
        RawItem(
            id=f"a{k}",
            source="jobs-adzuna",
            kind="job",
            title="x",
            url=f"https://x/{k}",
            extra={"market": "fr", "aggregate": True, "keyword": k, "count": n},
        )
        for k, n in (("RAG", 40), (None, 900))
    ]
    snaps = snapshot(agg, "2026-11", ["RAG", "MCP"])
    assert snaps[0].keyword_counts == {"RAG": 40, "MCP": 0}
    assert snaps[0].total_posts == 900


def test_notable_roles_are_most_frequent_titles():
    items = [job(str(n), title="ML Engineer") for n in range(3)] + [job("zz", title="Designer")]
    assert snapshot(items, "2026-11", [])[0].notable_roles[0] == "ml engineer"


def test_same_month_replaced_older_kept():
    old = JobSnapshot(
        id="global-jobs-hn-2026-10",
        month="2026-10",
        market="global",
        source="jobs-hn",
        total_posts=5,
        keyword_counts={},
    )
    prev = JobSnapshot(
        id="global-jobs-hn-2026-11",
        month="2026-11",
        market="global",
        source="jobs-hn",
        total_posts=1,
        keyword_counts={},
    )
    new = prev.model_copy(update={"total_posts": 9})
    merged = merge_snapshots({old.id: old, prev.id: prev}, [new])
    assert merged[new.id].total_posts == 9 and old.id in merged
