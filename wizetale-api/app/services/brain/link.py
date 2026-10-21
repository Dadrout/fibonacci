"""Concept linker: embedding candidates, LLM verification, strict threshold.

Never invents links: a pair is stored only if its embeddings are close
(BRAIN_LINK_CANDIDATE_SIMILARITY) AND the model judges it genuinely related with
strength ≥ BRAIN_LINK_MIN_STRENGTH. Cross-course candidates are considered first.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Sequence

from app.core.config import settings
from app.domain.brain.pipeline import LinkVerdict, LinkVerdicts
from app.services.brain.ai.client import AIUnavailable, BrainAI
from app.services.brain.store import BrainStore

logger = logging.getLogger(__name__)
MAX_PAIRS = 12
PER_CONCEPT = 4
MAX_PER_NEW_CONCEPT = 2  # keep the graph readable: the best one or two links per new idea


def _parse_vector(value: Any) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def candidate_pairs(store: BrainStore, uid: str, concepts: Sequence[dict], courses: dict[str, dict]) -> list[dict]:
    existing = {frozenset((l["source_concept_id"], l["target_concept_id"])) for l in store.links(uid, [c["id"] for c in concepts])}
    own_ids = [c["id"] for c in concepts]
    pairs, seen = [], set()
    for concept in concepts:
        vector = _parse_vector(concept.get("embedding"))
        if not vector:
            continue
        matches = store.match_concepts(uid, vector, exclude=own_ids, limit=8,
                                       min_similarity=settings.BRAIN_LINK_CANDIDATE_SIMILARITY)
        matches.sort(key=lambda m: (m["course_id"] == concept["course_id"], -m["similarity"]))
        for match in matches[:PER_CONCEPT]:
            key = frozenset((concept["id"], match["concept_id"]))
            if key in existing or key in seen:
                continue
            seen.add(key)
            pairs.append({"a": concept, "b": {"id": match["concept_id"], "course_id": match["course_id"], "name": match["name"],
                                              "summary": match["summary"]}, "similarity": match["similarity"]})
    pairs.sort(key=lambda p: (p["a"]["course_id"] == p["b"]["course_id"], -p["similarity"]))
    return pairs[:MAX_PAIRS]


def _side(concept: dict, courses: dict[str, dict]) -> dict:
    return {"name": concept["name"], "summary": concept.get("summary", ""), "course": courses.get(concept["course_id"], {}).get("title")}


def _pair_key(ai: BrainAI, a: dict, b: dict) -> str:
    return ai.cache.key("brain_link_pair", "v1", a["name"].lower(), a["course"], b["name"].lower(), b["course"])


def verify(pairs: list[dict], courses: dict[str, dict], ai: BrainAI) -> list[dict]:
    """Verdicts are cached per concept pair, so a pair judged once replays offline in any batch."""
    if not pairs:
        return []
    sides = [(_side(p["a"], courses), _side(p["b"], courses)) for p in pairs]
    known: dict[int, LinkVerdict] = {}
    unknown: list[int] = []
    for index, (a, b) in enumerate(sides):
        cached = ai.cache.get("brain_link_pair", _pair_key(ai, a, b))
        if cached is not None:
            known[index] = LinkVerdict.model_validate({**cached, "pair": index})
        else:
            unknown.append(index)
    if unknown:
        prompt_pairs = [{"pair": n, "a": sides[i][0], "b": sides[i][1]} for n, i in enumerate(unknown)]
        try:
            result = ai.generate(operation="brain_verify_links", prompt="verify_links", schema=LinkVerdicts,
                                 variables={"pairs": json.dumps(prompt_pairs, ensure_ascii=False)},
                                 model=settings.BRAIN_TEXT_MODEL, max_output_tokens=2048, temperature=0.1)
        except AIUnavailable:
            if not known:
                raise
            result = LinkVerdicts()
        for verdict in result.verdicts:
            if verdict.pair < len(unknown):
                index = unknown[verdict.pair]
                ai.cache.put("brain_link_pair", _pair_key(ai, *sides[index]), {**verdict.model_dump(), "pair": 0})
                known[index] = verdict.model_copy(update={"pair": index})
    verdicts = LinkVerdicts(verdicts=list(known.values()))
    links: list[dict] = []
    per_concept: dict[str, int] = {}
    ranked = sorted(verdicts.verdicts, key=lambda v: (-(v.pair < len(pairs) and pairs[v.pair]["a"]["course_id"] != pairs[v.pair]["b"]["course_id"]), -v.strength))
    for verdict in ranked:
        if verdict.pair >= len(pairs) or not verdict.related or not verdict.relation:
            continue
        if verdict.strength < settings.BRAIN_LINK_MIN_STRENGTH:
            continue
        pair = pairs[verdict.pair]
        if per_concept.get(pair["a"]["id"], 0) >= MAX_PER_NEW_CONCEPT:
            continue
        per_concept[pair["a"]["id"]] = per_concept.get(pair["a"]["id"], 0) + 1
        source, target = (pair["a"], pair["b"]) if verdict.direction == "a_to_b" else (pair["b"], pair["a"])
        links.append({"source_concept_id": source["id"], "target_concept_id": target["id"],
                      "strength": round(verdict.strength, 3), "relation": verdict.relation,
                      "rationale": verdict.rationale[:400], "method": "verified"})
    return links


def link_concepts(store: BrainStore, uid: str, concept_ids: Sequence[str], courses: dict[str, dict], ai: BrainAI) -> list[dict]:
    """Create verified links for the given concepts; returns the new link rows."""
    concepts = store.concepts(uid, ids=list(concept_ids), with_embedding=True)
    pairs = candidate_pairs(store, uid, concepts, courses)
    try:
        links = verify(pairs, courses, ai)
    except AIUnavailable:
        logger.info("brain_link verification_unavailable pairs=%d", len(pairs))
        return []
    created = store.add_links(uid, links)
    logger.info("brain_link candidates=%d verified=%d created=%d", len(pairs), len(links), len(created))
    return store.links_by_ids(uid, [i for i in created if i])
