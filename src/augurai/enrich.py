"""File-boundary contract with headless Claude Code: prepare the input, validate and merge the output."""

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from augurai.config import Settings
from augurai.domain.changes import Changes
from augurai.models import Entity, Model, Person, Practice, RawItem, Summary, WorkItem
from augurai.store import Store

ITEM_TEXT_LIMIT = 1500
SUMMARY_LIMIT = 300
SECTION_LIMIT = 1200
NOTE_LIMIT = 5
MAX_WORK_ITEMS = 20
MAX_MODELS = 15
EnrichStatus = Literal["ran", "partial", "failed", "skipped"]


class EnrichItem(BaseModel):
    id: str
    kind: str
    title: str
    url: str
    text: str = ""


class ModelBrief(BaseModel):
    id: str
    name: str
    provider: str
    scores: dict[str, dict[str, float]] = Field(default_factory=dict)
    best_at: list[str] = Field(default_factory=list)
    price_in: float | None = None
    price_out: float | None = None
    context_window: int | None = None


class PracticeRef(BaseModel):
    id: str
    title: str
    person_id: str


class EnrichInput(BaseModel):
    day: date
    items: list[EnrichItem] = Field(default_factory=list)
    new_people_work: list[WorkItem] = Field(default_factory=list)
    models: list[ModelBrief] = Field(default_factory=list)
    existing_practices: list[PracticeRef] = Field(default_factory=list)
    changes: Changes


class PracticeDraft(BaseModel):
    title: str
    principle: str
    how_to_apply: str
    person_id: str
    source_url: str
    related_skill: str | None = None
    tags: list[str] = Field(default_factory=list)
    reinforces: str | None = None


class ModelNote(BaseModel):
    use_cases: list[str] = Field(default_factory=list)
    avoid_for: list[str] = Field(default_factory=list)


class BriefingSection(BaseModel):
    title: str
    body_md: str


class BriefingText(BaseModel):
    headline: str
    sections: list[BriefingSection]
    practice_of_the_day: str


class EnrichOutput(BaseModel):
    summaries: dict[str, str] = Field(default_factory=dict)
    practices: list[PracticeDraft] = Field(default_factory=list)
    model_notes: dict[str, ModelNote] = Field(default_factory=dict)
    briefing: BriefingText | None = None


def content_hash(title: str, url: str) -> str:
    return hashlib.sha1(f"{title}\n{url}".encode()).hexdigest()[:16]


def _text(item: RawItem) -> str:
    extra = item.extra
    text = extra.get("text") or extra.get("description") or extra.get("summary") or item.title
    return str(text)[:ITEM_TEXT_LIMIT]


def prepare(
    store: Store, changes: Changes, items: list[RawItem], settings: Settings, out: Path
) -> EnrichInput:
    by_id = {i.id: i for i in items}
    cached = {s.id for s in store.read("summaries", Summary)}
    work_urls = {w.url for w in changes.people_work}

    ordered: list[str] = [i.id for i in items if i.url in work_urls and i.extra.get("person_id")]
    ordered += [eid for ids in changes.rising.values() for eid in ids]
    ordered += changes.top_hn + changes.top_papers

    selected: list[EnrichItem] = []
    seen: set[str] = set()
    for item_id in ordered:
        item = by_id.get(item_id)
        if item is None or item_id in seen or item_id in cached:
            continue
        seen.add(item_id)
        selected.append(
            EnrichItem(id=item.id, kind=item.kind, title=item.title, url=item.url, text=_text(item))
        )
        if len(selected) >= settings.max_enrich_items:
            break

    models = store.read_map("models", Model)
    model_ids = list(
        dict.fromkeys([*changes.new_models, *(m.model_id for m in changes.benchmark_moves)])
    )
    briefs = [
        ModelBrief(**models[mid].model_dump(include=set(ModelBrief.model_fields)))
        for mid in model_ids[:MAX_MODELS]
        if mid in models
    ]
    practices = [
        PracticeRef(id=p.id, title=p.title, person_id=p.person_id)
        for p in store.read("practices", Practice)
    ]
    enrich_input = EnrichInput(
        day=changes.day,
        items=selected,
        new_people_work=changes.people_work[:MAX_WORK_ITEMS],
        models=briefs,
        existing_practices=practices,
        changes=changes,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(enrich_input.model_dump_json(indent=2), encoding="utf-8")
    return enrich_input


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "practice"


def _validate_list(raw: object, model: type[BaseModel]) -> tuple[list, int]:
    kept, dropped = [], 0
    for entry in raw if isinstance(raw, list) else []:
        try:
            kept.append(model.model_validate(entry))
        except ValidationError:
            dropped += 1
    return kept, dropped


def merge(
    store: Store, output_path: Path, input_: EnrichInput, today: date
) -> tuple[EnrichStatus, str | None, BriefingText | None]:
    if not output_path.exists():
        return "skipped", None, None
    try:
        raw = json.loads(output_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return "failed", f"output is not valid JSON: {exc}"[:200], None
    if not isinstance(raw, dict):
        return "failed", "output is not a JSON object", None

    kept = dropped = 0
    known_items = {i.id for i in input_.items}

    summaries: dict[str, str] = {}
    for item_id, text in (
        (raw.get("summaries") or {}).items() if isinstance(raw.get("summaries"), dict) else []
    ):
        if item_id in known_items and isinstance(text, str) and text.strip():
            summaries[item_id] = text.strip()[:SUMMARY_LIMIT]
        else:
            dropped += 1
    if summaries:
        existing = store.read_map("summaries", Summary)
        existing.update({k: Summary(id=k, text=v) for k, v in summaries.items()})
        store.write("summaries", existing.values())
        entities = store.read_map("entities", Entity)
        changed = {
            k: e.model_copy(update={"summary": summaries[k]})
            for k, e in entities.items()
            if k in summaries
        }
        if changed:
            store.write("entities", {**entities, **changed}.values())
    kept += len(summaries)

    drafts, bad = _validate_list(raw.get("practices"), PracticeDraft)
    dropped += bad
    people = store.read_map("people", Person)
    work_urls = {w.url for w in input_.new_people_work}
    practices = store.read_map("practices", Practice)
    for draft in drafts:
        if draft.person_id not in people or draft.source_url not in work_urls:
            dropped += 1  # unknown person, or a source link that is not one of the input's own
            continue
        target = practices.get(draft.reinforces) if draft.reinforces else None
        if target is not None:
            if draft.source_url not in target.reinforced_by:
                practices[target.id] = target.model_copy(
                    update={"reinforced_by": [*target.reinforced_by, draft.source_url]}
                )
        else:
            base = _slug(draft.title)
            pid, n = base, 2
            while pid in practices:
                pid, n = f"{base}-{n}", n + 1
            practices[pid] = Practice(
                id=pid,
                title=draft.title,
                principle=draft.principle,
                how_to_apply=draft.how_to_apply,
                person_id=draft.person_id,
                source_url=draft.source_url,
                related_skill=draft.related_skill,
                tags=draft.tags,
                first_seen=today,
            )
        kept += 1
    store.write("practices", practices.values())

    models = store.read_map("models", Model)
    notes = raw.get("model_notes")
    for model_id, note_raw in notes.items() if isinstance(notes, dict) else []:
        try:
            note = ModelNote.model_validate(note_raw)
        except ValidationError:
            dropped += 1
            continue
        if model_id not in models:
            dropped += 1
            continue
        models[model_id] = models[model_id].model_copy(
            update={
                "use_cases": note.use_cases[:NOTE_LIMIT],
                "avoid_for": note.avoid_for[:NOTE_LIMIT],
            }
        )
        kept += 1
    store.write("models", models.values())

    briefing: BriefingText | None = None
    if raw.get("briefing") is not None:
        try:
            briefing = BriefingText.model_validate(raw["briefing"])
        except ValidationError:
            dropped += 1
        else:
            for section in briefing.sections:
                section.body_md = section.body_md[:SECTION_LIMIT]
            kept += 1

    if kept == 0 and dropped == 0:
        return "failed", "output contained nothing usable", None
    if dropped:
        return "partial", f"{dropped} item(s) dropped as invalid, {kept} kept", briefing
    return "ran", None, briefing
