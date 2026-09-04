"""Correlation validation and trace lifecycle orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from agentgate.domain import Case, Run, Trace, content_sha256
from agentgate.trace.merge import build_canonical_trace
from agentgate.trace.models import (
    IngestionReport, NormalizedSignal, NormalizedSpan, TraceBatch, TraceConflict,
)
from agentgate.trace.ordering import SpanOrderingError, order_spans


class TraceRepository(Protocol):
    def get_run(self, run_id: str) -> Run | None: ...
    def ingest_trace_batch(self, batch: TraceBatch) -> IngestionReport: ...
    def evaluate_trace_completeness(
        self, run_id: str, case_id: str, now: datetime
    ) -> Trace: ...
    def expire_trace(self, run_id: str, case_id: str, now: datetime) -> Trace: ...
    def expire_due_traces(self, now: datetime, limit: int = 100) -> tuple[Trace, ...]: ...


class TraceIngestionService:
    def __init__(self, repository: TraceRepository) -> None:
        self.repository = repository

    @staticmethod
    def classify_content(existing_sha256: str | None, incoming_sha256: str) -> str:
        """Apply the ingestion contract independently of any storage adapter."""
        if existing_sha256 is None:
            return "new"
        if existing_sha256 == incoming_sha256:
            return "duplicate"
        return "conflict"

    @staticmethod
    def classify_late_arrival(run: Run, has_evaluated_revision: bool) -> str:
        if not has_evaluated_revision:
            return "normal"
        return (
            "reject"
            if run.snapshot.trace_policy.late_arrival_policy == "reject"
            else "late_revision"
        )

    @staticmethod
    def should_create_revision(
        latest_content_sha256: str | None, candidate_content_sha256: str
    ) -> bool:
        return latest_content_sha256 != candidate_content_sha256

    @staticmethod
    def reconstruct(
        run: Run,
        case: Case,
        spans: list[NormalizedSpan],
        signals: list[NormalizedSignal],
        *,
        persisted_conflict_count: int,
        persisted_conflict_keys: set[tuple[str, str, str]] | None = None,
        revision: int,
        last_evidence_at: datetime | None,
        now: datetime,
        deadline_elapsed: bool = False,
    ) -> tuple[Trace, tuple[TraceConflict, ...]]:
        """Own merge, ordering, conflict and completeness domain decisions."""
        discovered: list[TraceConflict] = []
        persisted_conflict_keys = persisted_conflict_keys or set()

        def add_conflict(conflict: TraceConflict) -> None:
            key = (
                conflict.kind, conflict.original_sha256,
                conflict.conflicting_sha256,
            )
            if key not in persisted_conflict_keys:
                persisted_conflict_keys.add(key)
                discovered.append(conflict)
        try:
            order_spans(spans, {turn.id: i for i, turn in enumerate(case.turns)})
        except SpanOrderingError as exc:
            add_conflict(TraceConflict(
                kind="topology", run_id=run.id, case_id=case.id,
                conflicting_sha256=content_sha256(str(exc)), summary=str(exc),
                received_at=now,
            ))

        grouped: dict[tuple[str, str | None, int], list[NormalizedSignal]] = {}
        for signal in signals:
            grouped.setdefault(
                (signal.kind, signal.turn_id, signal.precedence), []
            ).append(signal)
        for (kind, turn_id, _precedence), candidates in grouped.items():
            hashes = sorted({content_sha256(item.value) for item in candidates})
            if len(hashes) > 1:
                add_conflict(TraceConflict(
                    kind="semantic_signal", run_id=run.id, case_id=case.id,
                    original_sha256=hashes[0], conflicting_sha256=hashes[-1],
                    summary=f"conflicting {kind} signals for turn {turn_id}",
                    received_at=now,
                ))

        trace = build_canonical_trace(
            run.id, case.id, spans, signals=signals, case=case,
            policy=run.snapshot.trace_policy,
            conflict_count=persisted_conflict_count + len(discovered),
            revision=revision, last_evidence_at=last_evidence_at, now=now,
            deadline_elapsed=deadline_elapsed,
        )
        return trace, tuple(discovered)

    def ingest(self, batch: TraceBatch) -> IngestionReport:
        accepted_spans = []
        accepted_signals = []
        accepted_sources: set[tuple[str, str, str, str]] = set()
        errors = list(batch.errors)
        rejected = batch.rejected_spans
        run_cache: dict[str, Run | None] = {}
        case_cache = {}

        def resolve(run_id: str, case_id: str):
            run = run_cache.setdefault(run_id, self.repository.get_run(run_id))
            if run is None:
                return None, None, f"unknown run {run_id}"
            key = (run_id, case_id)
            case = case_cache.get(key)
            if case is None:
                case = next(
                    (item for item in run.snapshot.dataset.cases if item.id == case_id), None
                )
                case_cache[key] = case
            if case is None:
                return run, None, f"case {case_id} is not in run"
            return run, case, None

        for index, span in enumerate(batch.spans, start=1):
            _run, case, error = resolve(span.run_id, span.case_id)
            if error:
                rejected += 1
                if len(errors) < 20:
                    errors.append(f"normalized span {index}: {error}")
                continue
            turn_ids = {turn.id for turn in case.turns}
            normalized_span = span
            if span.turn_id is None:
                if len(case.turns) == 1:
                    normalized_span = span.model_copy(update={
                        "turn_id": case.turns[0].id,
                    })
                else:
                    rejected += 1
                    if len(errors) < 20:
                        errors.append(
                            f"normalized span {index}: multi-turn case requires turn_id"
                        )
                    continue
            if normalized_span.turn_id not in turn_ids:
                rejected += 1
                if len(errors) < 20:
                    errors.append(
                        f"normalized span {index}: turn {normalized_span.turn_id} "
                        "is not in case"
                    )
                continue
            target_expectations = {
                "agentgate.target.type": _run.snapshot.target.ref.target_type.value,
                "agentgate.target.id": _run.snapshot.target.ref.external_target_id,
                "agentgate.target.version": _run.snapshot.target.ref.external_version_id,
            }
            mismatch = next((
                key for key, expected in target_expectations.items()
                if key in normalized_span.attributes
                and normalized_span.attributes[key] != expected
            ), None)
            if mismatch:
                rejected += 1
                if len(errors) < 20:
                    errors.append(
                        f"normalized span {index}: {mismatch} does not match TargetSnapshot"
                    )
                continue
            accepted_spans.append(normalized_span)
            accepted_sources.add((
                normalized_span.run_id, normalized_span.case_id,
                normalized_span.source_trace_id, normalized_span.source_span_id,
            ))

        for index, signal in enumerate(batch.signals, start=1):
            source = (
                signal.run_id, signal.case_id,
                signal.source_trace_id, signal.source_span_id,
            )
            if source not in accepted_sources:
                if len(errors) < 20:
                    errors.append(
                        f"normalized signal {index}: source span was rejected"
                    )
                continue
            _run, case, error = resolve(signal.run_id, signal.case_id)
            if error:
                if len(errors) < 20:
                    errors.append(f"normalized signal {index}: {error}")
                continue
            turn_ids = {turn.id for turn in case.turns}
            normalized = signal
            if signal.turn_id is None and len(case.turns) == 1 and signal.kind != "trace_complete":
                normalized = signal.model_copy(update={
                    "turn_id": case.turns[0].id, "id": "", "content_sha256": "",
                })
                normalized = type(signal).model_validate(normalized.model_dump(mode="json"))
            if (
                normalized.turn_id is None
                and len(case.turns) > 1
                and normalized.kind != "trace_complete"
            ):
                if len(errors) < 20:
                    errors.append(
                        f"normalized signal {index}: multi-turn case requires turn_id"
                    )
                continue
            if normalized.turn_id is not None and normalized.turn_id not in turn_ids:
                if len(errors) < 20:
                    errors.append(
                        f"normalized signal {index}: turn {normalized.turn_id} is not in case"
                    )
                continue
            if normalized.kind == "turn_complete" and normalized.turn_id is None:
                if len(errors) < 20:
                    errors.append(f"normalized signal {index}: turn_complete requires turn_id")
                continue
            accepted_signals.append(normalized)

        validated = batch.model_copy(update={
            "spans": tuple(accepted_spans), "signals": tuple(accepted_signals),
            "rejected_spans": rejected, "errors": tuple(errors[:20]),
        })
        return self.repository.ingest_trace_batch(validated)

    def evaluate_trace_completeness(
        self, run_id: str, case_id: str, now: datetime | None = None
    ) -> Trace:
        return self.repository.evaluate_trace_completeness(
            run_id, case_id, now or datetime.now(UTC)
        )

    def expire_trace(
        self, run_id: str, case_id: str, now: datetime | None = None
    ) -> Trace:
        return self.repository.expire_trace(run_id, case_id, now or datetime.now(UTC))

    def expire_due_traces(
        self, now: datetime | None = None, limit: int = 100
    ) -> tuple[Trace, ...]:
        return self.repository.expire_due_traces(now or datetime.now(UTC), limit)
