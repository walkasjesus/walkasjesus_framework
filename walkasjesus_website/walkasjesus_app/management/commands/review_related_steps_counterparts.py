from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand

from walkasjesus_app.models import (
    Commandment,
    DirectBibleReference,
    DuplicateBibleReference,
    ExampleBibleReference,
    IndirectBibleReference,
    LawOfMessiah,
    LawOfMessiahBibleReference,
    OTLawBibleReference,
    PrimaryBibleReference,
    StudyBibleReference,
    WisdomBibleReference,
)


@dataclass
class MatchScore:
    law: LawOfMessiah
    score: float
    exact_overlap: int
    chapter_overlap: int
    text_similarity: float
    relation_bonus: float
    user_suggestion: bool = False  # True when the law was originally linked to this step by the user


def _normalize_end_chapter(begin_chapter, end_chapter):
    return begin_chapter if not end_chapter else end_chapter


def _normalize_end_verse(begin_verse, end_verse):
    return begin_verse if not end_verse else end_verse


def _reference_tokens(ref):
    end_chapter = _normalize_end_chapter(ref.begin_chapter, ref.end_chapter)
    end_verse = _normalize_end_verse(ref.begin_verse, ref.end_verse)
    exact = f"{ref.book}:{ref.begin_chapter}:{ref.begin_verse}:{end_chapter}:{end_verse}"
    chapter = f"{ref.book}:{ref.begin_chapter}"
    return exact, chapter


def _jaccard_overlap(left, right):
    if not left or not right:
        return 0.0
    intersect = len(left.intersection(right))
    union = len(left.union(right))
    return (intersect / union) if union else 0.0


def _title_similarity(step_title, law):
    law_text = f"{law.title} {law.commandment}".strip().lower()
    return SequenceMatcher(None, (step_title or "").lower(), law_text).ratio()


class Command(BaseCommand):
    help = (
        "Build a review file that proposes Law of Messiah counterparts for each related step "
        "using Bible-reference overlap and text similarity."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default="data/lawofmessiah/filter_output/review_related_steps_counterparts.yaml",
            help="Path to write the review YAML file.",
        )
        parser.add_argument(
            "--candidate-count",
            type=int,
            default=7,
            help="How many top candidate laws to include per step.",
        )
        parser.add_argument(
            "--laws-scope",
            choices=["all", "unique-positive"],
            default="unique-positive",
            help="Candidate law scope.",
        )
        parser.add_argument(
            "--steps-scope",
            choices=["all-linked", "linked-from-unique-positive", "all-commandments"],
            default="all-commandments",
            help="Which steps to review.",
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"])
        candidate_count = max(1, int(options["candidate_count"]))
        laws_scope = options["laws_scope"]
        steps_scope = options["steps_scope"]

        candidate_laws = self._get_candidate_laws(laws_scope)
        step_ids = self._get_step_ids(steps_scope)
        steps = list(Commandment.objects.filter(id__in=step_ids).order_by("id"))

        if not steps:
            self.stdout.write(self.style.WARNING("No steps found for the requested scope."))
            return

        step_ref_data = self._build_step_reference_index(step_ids)
        law_ref_data = self._build_law_reference_index(candidate_laws)
        law_to_existing_steps = self._build_existing_relation_index(step_ids)

        # Laws linked to steps but outside the candidate scope (e.g. is_unique=False)
        candidate_law_ids = {law.id for law in candidate_laws}
        user_linked_extras = self._build_user_linked_extras(step_ids, candidate_law_ids)
        law_ref_data_extras = self._build_law_reference_index(
            [law for laws in user_linked_extras.values() for law in laws]
        )
        law_ref_data_extras["exact"].update(law_ref_data["exact"])
        law_ref_data_extras["chapter"].update(law_ref_data["chapter"])

        top_per_step = {}
        full_per_step = {}  # full ranked list used for alternatives in one_to_one
        review_rows = []
        for step in steps:
            all_matches = self._score_step_against_laws(
                step=step,
                candidate_laws=candidate_laws,
                step_ref_data=step_ref_data,
                law_ref_data=law_ref_data,
                law_to_existing_steps=law_to_existing_steps,
            )
            # Inject user-linked laws that are outside the candidate scope
            extras = self._score_extra_linked_laws(
                step=step,
                extra_laws=user_linked_extras.get(step.id, []),
                step_ref_data=step_ref_data,
                law_ref_data=law_ref_data_extras,
            )
            if extras:
                # Put them right after the top-N block so they're always visible
                top_n = all_matches[:candidate_count]
                rest = [m for m in all_matches[candidate_count:] if m.law.id not in {e.law.id for e in extras}]
                all_matches = top_n + extras + rest
            # Also guarantee in-scope already-linked laws stay in top-N
            all_matches = self._ensure_linked_laws_included(
                all_matches, step.id, law_to_existing_steps, candidate_count
            )
            top_per_step[step.id] = all_matches[:candidate_count]
            full_per_step[step.id] = all_matches
            review_rows.append(self._serialize_step_review(step, all_matches[:candidate_count], law_to_existing_steps))

        one_to_one = self._build_one_to_one_suggestion(steps, top_per_step, full_per_step)

        payload = {
            "meta": {
                "generator": "manage.py review_related_steps_counterparts",
                "steps_scope": steps_scope,
                "laws_scope": laws_scope,
                "steps_count": len(steps),
                "candidate_laws_count": len(candidate_laws),
                "candidate_count_per_step": candidate_count,
                "expected_target_count": 77,
            },
            "summary": {
                "steps_with_candidates": sum(1 for row in review_rows if row["top_candidates"]),
                "one_to_one_unique_counterparts": len({row["proposed_law_id"] for row in one_to_one if row.get("proposed_law_id")}),
                "one_to_one_rows": len(one_to_one),
            },
            "one_to_one_suggestion": one_to_one,
            "step_reviews": review_rows,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=False, width=140)

        self.stdout.write(self.style.SUCCESS(f"Wrote review file: {output_path}"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Steps={len(steps)}, candidate_laws={len(candidate_laws)}, one_to_one_unique={payload['summary']['one_to_one_unique_counterparts']}"
            )
        )

    def _get_candidate_laws(self, laws_scope):
        laws = LawOfMessiah.objects.all().order_by("id")
        if laws_scope == "unique-positive":
            laws = laws.filter(is_unique=True, commandment_type=LawOfMessiah.COMMANDMENT_TYPE_POSITIVE)
        return list(laws)

    def _get_step_ids(self, steps_scope):
        if steps_scope == "all-commandments":
            return list(Commandment.objects.order_by("id").values_list("id", flat=True))

        if steps_scope == "all-linked":
            return sorted(
                set(
                    LawOfMessiah.objects.filter(related_steps__isnull=False)
                    .values_list("related_steps__id", flat=True)
                )
                - {None}
            )

        return sorted(
            set(
                LawOfMessiah.objects.filter(
                    is_unique=True,
                    commandment_type=LawOfMessiah.COMMANDMENT_TYPE_POSITIVE,
                    related_steps__isnull=False,
                ).values_list("related_steps__id", flat=True)
            )
            - {None}
        )

    def _build_step_reference_index(self, step_ids):
        models = [
            PrimaryBibleReference,
            DirectBibleReference,
            IndirectBibleReference,
            DuplicateBibleReference,
            ExampleBibleReference,
            StudyBibleReference,
            OTLawBibleReference,
            WisdomBibleReference,
        ]
        exact_refs = defaultdict(set)
        chapter_refs = defaultdict(set)

        for model in models:
            for ref in model.objects.filter(commandment_id__in=step_ids):
                exact, chapter = _reference_tokens(ref)
                exact_refs[ref.commandment_id].add(exact)
                chapter_refs[ref.commandment_id].add(chapter)

        return {"exact": exact_refs, "chapter": chapter_refs}

    def _build_law_reference_index(self, candidate_laws):
        law_ids = [law.id for law in candidate_laws]
        exact_refs = defaultdict(set)
        chapter_refs = defaultdict(set)

        rows = LawOfMessiahBibleReference.objects.filter(law_of_messiah_id__in=law_ids) if law_ids else []
        for ref in rows:
            exact, chapter = _reference_tokens(ref)
            exact_refs[ref.law_of_messiah_id].add(exact)
            chapter_refs[ref.law_of_messiah_id].add(chapter)

        return {"exact": exact_refs, "chapter": chapter_refs}

    def _build_existing_relation_index(self, step_ids):
        index = defaultdict(set)
        for law_id, step_id in LawOfMessiah.objects.filter(related_steps__id__in=step_ids).values_list("id", "related_steps__id"):
            index[law_id].add(step_id)
        return index

    def _build_user_linked_extras(self, step_ids, candidate_law_ids):
        """Laws that are linked to a step via related_steps but fall outside the candidate scope."""
        extra_ids_by_step = defaultdict(set)
        for law_id, step_id in LawOfMessiah.objects.filter(
            related_steps__id__in=step_ids
        ).values_list("id", "related_steps__id"):
            if law_id not in candidate_law_ids:
                extra_ids_by_step[step_id].add(law_id)

        all_extra_ids = {lid for ids in extra_ids_by_step.values() for lid in ids}
        extra_law_objects = {law.id: law for law in LawOfMessiah.objects.filter(id__in=all_extra_ids)}

        return {
            step_id: [extra_law_objects[lid] for lid in law_ids if lid in extra_law_objects]
            for step_id, law_ids in extra_ids_by_step.items()
        }

    def _score_extra_linked_laws(self, step, extra_laws, step_ref_data, law_ref_data):
        """Score user-linked laws that are outside the candidate scope and mark them as user_suggestion."""
        step_exact = step_ref_data["exact"].get(step.id, set())
        step_chapter = step_ref_data["chapter"].get(step.id, set())
        scored = []
        for law in extra_laws:
            law_exact = law_ref_data["exact"].get(law.id, set())
            law_chapter = law_ref_data["chapter"].get(law.id, set())
            exact_overlap_count = len(step_exact.intersection(law_exact))
            chapter_overlap_count = len(step_chapter.intersection(law_chapter))
            exact_overlap_score = _jaccard_overlap(step_exact, law_exact)
            chapter_overlap_score = _jaccard_overlap(step_chapter, law_chapter)
            text_similarity = _title_similarity(step.title, law)
            score = (
                (exact_overlap_score * 0.55)
                + (chapter_overlap_score * 0.2)
                + (text_similarity * 0.25)
                + 0.15  # relation bonus always applies here
            )
            scored.append(MatchScore(
                law=law,
                score=round(score, 6),
                exact_overlap=exact_overlap_count,
                chapter_overlap=chapter_overlap_count,
                text_similarity=round(text_similarity, 6),
                relation_bonus=0.15,
                user_suggestion=True,
            ))
        scored.sort(key=lambda m: m.score, reverse=True)
        return scored

    def _ensure_linked_laws_included(self, matches, step_id, law_to_existing_steps, candidate_count):
        """Guarantee laws that are already linked to this step appear in the top-N candidates."""
        already_linked_ids = {
            law_id
            for law_id, step_ids in law_to_existing_steps.items()
            if step_id in step_ids
        }
        if not already_linked_ids:
            return matches

        top_n_ids = {m.law.id for m in matches[:candidate_count]}
        missing = already_linked_ids - top_n_ids
        if not missing:
            return matches

        # Inject the missing linked laws right after the top-N block, preserving their relative rank
        top_n = matches[:candidate_count]
        rest = matches[candidate_count:]
        missing_entries = [m for m in rest if m.law.id in missing]
        other_rest = [m for m in rest if m.law.id not in missing]
        return top_n + missing_entries + other_rest

    def _score_step_against_laws(self, step, candidate_laws, step_ref_data, law_ref_data, law_to_existing_steps):
        step_exact = step_ref_data["exact"].get(step.id, set())
        step_chapter = step_ref_data["chapter"].get(step.id, set())

        scored = []
        for law in candidate_laws:
            law_exact = law_ref_data["exact"].get(law.id, set())
            law_chapter = law_ref_data["chapter"].get(law.id, set())

            exact_overlap_count = len(step_exact.intersection(law_exact))
            chapter_overlap_count = len(step_chapter.intersection(law_chapter))

            exact_overlap_score = _jaccard_overlap(step_exact, law_exact)
            chapter_overlap_score = _jaccard_overlap(step_chapter, law_chapter)
            text_similarity = _title_similarity(step.title, law)
            relation_bonus = 0.15 if step.id in law_to_existing_steps.get(law.id, set()) else 0.0

            score = (
                (exact_overlap_score * 0.55)
                + (chapter_overlap_score * 0.2)
                + (text_similarity * 0.25)
                + relation_bonus
            )

            scored.append(
                MatchScore(
                    law=law,
                    score=round(score, 6),
                    exact_overlap=exact_overlap_count,
                    chapter_overlap=chapter_overlap_count,
                    text_similarity=round(text_similarity, 6),
                    relation_bonus=relation_bonus,
                )
            )

        scored.sort(
            key=lambda item: (
                item.score,
                item.exact_overlap,
                item.chapter_overlap,
                item.text_similarity,
            ),
            reverse=True,
        )
        return scored

    def _serialize_step_review(self, step, matches, law_to_existing_steps):
        candidates = []
        for match in matches:
            candidates.append(
                {
                    "law_id": match.law.id,
                    "law_title": match.law.title,
                    "score": match.score,
                    "exact_overlap_count": match.exact_overlap,
                    "chapter_overlap_count": match.chapter_overlap,
                    "text_similarity": match.text_similarity,
                    "already_linked_step": step.id in law_to_existing_steps.get(match.law.id, set()),
                    "user_suggestion": match.user_suggestion,
                }
            )

        row = {
            "step_id": str(step.id),
            "step_title": step.title,
            "proposed_law_id": candidates[0]["law_id"] if candidates else None,
            "proposed_law_title": candidates[0]["law_title"] if candidates else None,
            "review_status": "pending",
            "review_notes": "",
            "top_candidates": candidates,
        }
        return row

    def _build_one_to_one_suggestion(self, steps, top_per_step, full_per_step, alternatives_count=5):
        # Greedy assignment: stronger matches first, avoid reusing laws.
        steps_by_id = {step.id: step for step in steps}
        step_priority = []
        for step in steps:
            candidates = top_per_step.get(step.id, [])
            best = candidates[0].score if candidates else 0.0
            gap = (candidates[0].score - candidates[1].score) if len(candidates) > 1 else candidates[0].score if candidates else 0.0
            step_priority.append((best, gap, step.id))

        step_priority.sort(reverse=True)
        used_laws = set()
        result = []

        for _, _, step_id in step_priority:
            step = steps_by_id[step_id]
            chosen = None
            for candidate in top_per_step.get(step_id, []):
                if candidate.law.id not in used_laws:
                    chosen = candidate
                    break

            if chosen:
                used_laws.add(chosen.law.id)
                # Build alternatives: always include user_suggestion entries first,
                # then fill remaining slots with highest-scoring others.
                full_other = [
                    {
                        "law_id": m.law.id,
                        "law_title": m.law.title,
                        "score": m.score,
                        "already_linked": m.relation_bonus > 0,
                        "user_suggestion": m.user_suggestion,
                    }
                    for m in full_per_step.get(step_id, [])
                    if m.law.id != chosen.law.id
                ]
                user_alts = [a for a in full_other if a["user_suggestion"]]
                regular_alts = [a for a in full_other if not a["user_suggestion"]]
                remaining = max(0, alternatives_count - len(user_alts))
                alts = user_alts + regular_alts[:remaining]
                result.append(
                    {
                        "step_id": str(step.id),
                        "step_title": step.title,
                        "proposed_law_id": chosen.law.id,
                        "proposed_law_title": chosen.law.title,
                        "score": chosen.score,
                        "already_linked": chosen.relation_bonus > 0,
                        "alternatives": alts,
                        "review_status": "pending",
                        "review_notes": "",
                    }
                )
            else:
                result.append(
                    {
                        "step_id": str(step.id),
                        "step_title": step.title,
                        "proposed_law_id": None,
                        "proposed_law_title": None,
                        "score": 0.0,
                        "already_linked": False,
                        "alternatives": [],
                        "review_status": "pending",
                        "review_notes": "No unused candidate available in top list. Increase --candidate-count.",
                    }
                )

        result.sort(key=lambda item: int(item["step_id"]))
        return result
