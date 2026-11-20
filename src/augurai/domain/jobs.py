"""Monthly job-market snapshots: keyword demand per market and source."""

import re
from collections import Counter

from augurai.models import JobSnapshot, RawItem

NOTABLE_ROLES = 5


def _pattern(keyword: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(keyword)}(?![A-Za-z0-9])", re.IGNORECASE)


def snapshot(items: list[RawItem], month: str, keywords: list[str]) -> list[JobSnapshot]:
    groups: dict[tuple[str, str], list[RawItem]] = {}
    for item in items:
        if item.kind != "job":
            continue
        market = str(item.extra.get("market", "global"))
        groups.setdefault((market, item.source), []).append(item)

    patterns = {kw: _pattern(kw) for kw in keywords}
    snapshots: list[JobSnapshot] = []
    for (market, source), group in sorted(groups.items()):
        postings = [i for i in group if not i.extra.get("aggregate")]
        aggregates = [i for i in group if i.extra.get("aggregate")]
        counts = {kw: 0 for kw in keywords}
        for item in postings:
            text = str(item.extra.get("text", item.title))
            for kw, pattern in patterns.items():
                if pattern.search(text):
                    counts[kw] += 1
        total = len(postings)
        for agg in aggregates:
            keyword = agg.extra.get("keyword")
            if keyword is None:
                total = int(agg.extra.get("count", total))
            elif keyword in counts:
                counts[keyword] = int(agg.extra.get("count", 0))
        roles = Counter(i.title.strip().lower() for i in postings if i.title.strip())
        snapshots.append(
            JobSnapshot(
                id=f"{market}-{source}-{month}",
                month=month,
                market=market,  # type: ignore[arg-type]
                source=source,
                total_posts=total,
                keyword_counts=counts,
                notable_roles=[role for role, _ in roles.most_common(NOTABLE_ROLES)],
            )
        )
    return snapshots


def merge_snapshots(
    existing: dict[str, JobSnapshot], new: list[JobSnapshot]
) -> dict[str, JobSnapshot]:
    merged = dict(existing)
    for snap in new:
        merged[snap.id] = snap
    return merged
