"""Local control-plane service shared by CLI, HTTP, and the Web UI."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

LOGGER = logging.getLogger(__name__)

from agentgate.case import DatasetService
from agentgate.demo.loan import LOAN_DATASET, LOAN_DATASET_VERSION, LoanAgent
from agentgate.domain import (
    Case,
    CaseProvenance,
    Dataset,
    DatasetPurpose,
    DatasetVersion,
    RunStatus,
    TargetRef,
    TargetSnapshot,
    TargetType,
    freeze_json,
)
from agentgate.evaluator import EVALUATORS
from agentgate.evaluator import validation as evaluator_validation
from agentgate.run.core import RunEngine
from agentgate.run.targets.base import (
    EnvCredentialResolver,
    TargetExecutionAdapter,
    TargetIntegrationError,
)
from agentgate.run.targets.http import HttpTargetAdapter
from agentgate.run.targets.python_fn import PythonFunctionTarget
from agentgate.storage.base import AgentGateRepository


@dataclass
class TargetRegistration:
    target_id: str
    label: str
    adapter_type: str
    target_ref: TargetRef
    invocation_config: dict
    credential_ref: str | None = None
    is_latest: bool = False

    def build(
        self, repository: AgentGateRepository
    ) -> tuple[TargetSnapshot, TargetExecutionAdapter]:
        snapshot = TargetSnapshot(
            ref=self.target_ref,
            display_name=self.label,
            adapter_type=self.adapter_type,
            adapter_version="1",
            invocation_config=freeze_json(self.invocation_config),
            credential_ref=self.credential_ref,
        )
        if self.adapter_type == "python_fn":
            adapter: TargetExecutionAdapter = PythonFunctionTarget(LoanAgent(repository).execute)
        elif self.adapter_type == "http":
            endpoint = self.invocation_config.get("endpoint", "")
            adapter = HttpTargetAdapter(endpoint, EnvCredentialResolver())
        else:
            raise ValueError(f"unknown adapter type: {self.adapter_type}")
        return snapshot, adapter


def _build_registry() -> dict[str, TargetRegistration]:
    return {
        reg.target_id: reg
        for reg in (
            TargetRegistration(
                target_id="loan-agent-v1-risky",
                label="风险版本",
                adapter_type="python_fn",
                target_ref=TargetRef(
                    platform_id="demo",
                    target_type=TargetType.AGENT,
                    external_target_id="loan-agent",
                    external_version_id="loan-agent-v1-risky",
                ),
                invocation_config={},
            ),
            TargetRegistration(
                target_id="loan-agent-v2-fixed",
                label="修复版本",
                adapter_type="python_fn",
                target_ref=TargetRef(
                    platform_id="demo",
                    target_type=TargetType.AGENT,
                    external_target_id="loan-agent",
                    external_version_id="loan-agent-v2-fixed",
                ),
                invocation_config={},
                is_latest=True,
            ),
            TargetRegistration(
                target_id="langchain-http-agent",
                label="LangChain HTTP Agent",
                adapter_type="http",
                target_ref=TargetRef(
                    platform_id="langchain",
                    target_type=TargetType.AGENT,
                    external_target_id="langchain-agent",
                    external_version_id="v1",
                ),
                invocation_config={
                    "endpoint": "http://localhost:8081/invoke",
                    "timeout_seconds": 900.0,
                },
                credential_ref="AGENTGATE_LANGCHAIN_API_KEY",
            ),
        )
    }


class EvaluationService:
    """Coordinate evaluation launches and read models for the local POC."""

    def __init__(
        self,
        repository: AgentGateRepository,
        registration_provider: Callable[[], Sequence[TargetRegistration]] | None = None,
    ) -> None:
        self.repository = repository
        self.engine = RunEngine(repository)
        self.dataset_service = DatasetService(repository)
        self.dataset_service.seed(LOAN_DATASET, LOAN_DATASET_VERSION)
        self._registration_provider = registration_provider

    @property
    def _registry(self) -> dict[str, TargetRegistration]:
        """注册表：demo 硬编码注册 + DB 注册（同 id 时 DB 优先）。

        provider 失败时仅记录告警并回落到 demo 注册，保证启动/回退安全。
        """
        registry = _build_registry()
        provider = self._registration_provider
        if provider is not None:
            try:
                for registration in provider():
                    registry[registration.target_id] = registration
            except Exception as exc:  # noqa: BLE001 - 注册表不可用时保底
                LOGGER.warning(
                    "target registration provider failed, "
                    "falling back to demo registry only: %s", exc,
                )
        return registry

    def _find_registration_by_version(self, version: str) -> TargetRegistration | None:
        for reg in self._registry.values():
            if reg.target_ref.external_version_id == version:
                return reg
        return None

    def launch_target(
        self, snapshot: TargetSnapshot, adapter: TargetExecutionAdapter,
        dataset_id: str | None = None, dataset_version: int | None = None,
        evaluator_ids: list[str] | None = None,
        trace_wait_seconds: float = 30.0,
        trace_poll_interval_seconds: float = 0.5,
    ):
        dataset_id = dataset_id or LOAN_DATASET.id
        dataset = (
            self.dataset_service.get_version(dataset_id, dataset_version)
            if dataset_version is not None
            else self.dataset_service.latest_published(dataset_id)
        )
        selected = EVALUATORS if evaluator_ids is None else tuple(
            item for item in EVALUATORS if item.id in evaluator_ids
        )
        if not selected:
            raise ValueError("at least one evaluator is required")
        unknown = set(evaluator_ids or ()) - {item.id for item in EVALUATORS}
        if unknown:
            raise ValueError(f"unknown evaluators: {', '.join(sorted(unknown))}")
        return self.engine.run(
            dataset, snapshot, adapter, selected,
            trace_wait_seconds=trace_wait_seconds,
            trace_poll_interval_seconds=trace_poll_interval_seconds,
        )

    def launch(
        self, target_id: str, dataset_id: str | None = None,
        dataset_version: int | None = None, evaluator_ids: list[str] | None = None,
    ):
        registration = self._registry.get(target_id)
        if registration is None:
            raise TargetIntegrationError.target_not_found(f"unknown target: {target_id}")
        snapshot, adapter = registration.build(self.repository)
        return self.launch_target(
            snapshot, adapter, dataset_id, dataset_version, evaluator_ids
        )

    def launch_http(
        self, target_ref: TargetRef, endpoint: str,
        credential_ref: str | None, dataset_id: str | None = None,
        dataset_version: int | None = None,
        evaluator_ids: list[str] | None = None,
        timeout_seconds: float = 30.0, trace_wait_seconds: float = 30.0,
    ):
        snapshot = TargetSnapshot(
            ref=target_ref,
            display_name=target_ref.external_target_id,
            adapter_type="http",
            adapter_version="1",
            invocation_config=freeze_json({
                "endpoint": endpoint,
                "timeout_seconds": timeout_seconds,
            }),
            credential_ref=credential_ref,
        )
        adapter = HttpTargetAdapter(endpoint, EnvCredentialResolver())
        return self.launch_target(
            snapshot, adapter, dataset_id, dataset_version, evaluator_ids,
            trace_wait_seconds=trace_wait_seconds,
        )

    def overview(self) -> dict:
        runs = self.repository.list_runs()
        completed = [run for run in runs if run.status == "completed"]
        latest = self.engine.report(runs[0].id) if runs else None
        case_count = sum(
            len(version.cases)
            for dataset in self.dataset_service.list_datasets()
            if (version := self.repository.get_latest_dataset_version(dataset.id)) is not None
        )
        return {
            "total_runs": len(runs),
            "completed_runs": len(completed),
            "case_count": case_count,
            "latest": latest,
        }

    def run_detail(self, run_id: str):
        return self.engine.report(run_id)

    def add_case_to_regression_dataset(
        self, *, run_id: str, case_id: str,
        regression_dataset_id: str | None,
        new_dataset_name: str | None,
        new_dataset_description: str = "",
        reason: str = "",
    ) -> tuple[Dataset, DatasetVersion, Case]:
        if (regression_dataset_id is None) == (new_dataset_name is None):
            raise ValueError("choose exactly one regression Dataset target")
        source_run = self.repository.get_run(run_id)
        if source_run is None:
            raise LookupError("run not found")
        if source_run.status != RunStatus.COMPLETED:
            raise ValueError("only completed Runs can add regression Cases")
        source_case = next(
            (item for item in source_run.snapshot.dataset.cases if item.id == case_id),
            None,
        )
        if source_case is None:
            raise LookupError("case not found in source Run snapshot")
        source_version = source_run.snapshot.dataset.version
        if source_version is None:
            raise ValueError("source Run Dataset must be published")
        source_case_id = (
            source_case.provenance.source_case_id
            if source_case.provenance is not None
            else source_case.id
        )
        copied = source_case.model_copy(update={
            "id": str(uuid4()),
            "provenance": CaseProvenance(
                source_run_id=source_run.id,
                source_dataset_id=source_run.snapshot.dataset.dataset_id,
                source_dataset_version=source_version,
                source_case_id=source_case_id,
                captured_at=datetime.now(UTC),
                reason=reason.strip(),
            ),
        })

        if regression_dataset_id is None:
            name = (new_dataset_name or "").strip()
            if not name:
                raise ValueError("regression Dataset name is required")
            dataset = Dataset(
                name=name,
                description=new_dataset_description.strip(),
                purpose=DatasetPurpose.REGRESSION,
            )
            draft = DatasetVersion(
                dataset_id=dataset.id,
                dataset_name=dataset.name,
                dataset_description=dataset.description,
                cases=(copied,),
            )
            self.repository.save_dataset_with_draft(dataset, draft)
            return dataset, draft, copied

        try:
            dataset = self.dataset_service.get_dataset(regression_dataset_id)
        except ValueError as exc:
            raise LookupError("regression Dataset not found") from exc
        if dataset.archived:
            raise ValueError("archived regression Dataset cannot be edited")
        if dataset.purpose != DatasetPurpose.REGRESSION:
            raise ValueError("target must be a regression Dataset")
        draft = self.dataset_service.get_draft(dataset.id)
        effective_cases = (
            draft.cases
            if draft is not None
            else (
                self.repository.get_latest_dataset_version(dataset.id).cases
                if self.repository.get_latest_dataset_version(dataset.id) is not None
                else ()
            )
        )
        if any(
            item.provenance is not None
            and item.provenance.source_case_id == source_case_id
            for item in effective_cases
        ):
            raise ValueError("source Case already exists in regression Dataset")
        if draft is None:
            draft = self.dataset_service.create_draft(dataset.id)
        updated = self.dataset_service.save_case(dataset.id, copied)
        return dataset, updated, copied

    def rerun_case(
        self, run_id: str, case_id: str, target_version: str | None = None,
    ):
        source = self.repository.get_run(run_id)
        if source is None:
            raise LookupError("run not found")
        if source.status != "completed":
            raise ValueError("only completed Runs can be rerun")
        case = next(
            (item for item in source.snapshot.dataset.cases if item.id == case_id), None
        )
        if case is None:
            raise LookupError("case not found in source Run snapshot")
        version = target_version or self.latest_target_version()
        registration = self._find_registration_by_version(version)
        if registration is None:
            raise TargetIntegrationError.version_not_found(
                f"unknown target version: {version}"
            )
        _, adapter = registration.build(self.repository)
        target_snapshot = source.snapshot.target.model_copy(
            update={
                "ref": source.snapshot.target.ref.model_copy(
                    update={"external_version_id": version}
                ),
                "content_sha256": "",
            }
        )
        return self.engine.run(
            source.snapshot.dataset,
            target_snapshot,
            adapter,
            evaluators=source.snapshot.evaluator_specs,
            metric_plan=source.snapshot.metric_plan,
            gate_spec=source.snapshot.gate_spec,
            selected_case_ids=(case.id,),
            parent_run_id=source.id,
            root_run_id=source.root_run_id or source.id,
            rerun_case_id=case.id,
        )

    def latest_target_version(self) -> str:
        for reg in self._registry.values():
            if reg.is_latest:
                return reg.target_ref.external_version_id
        return next(iter(self._registry.values())).target_ref.external_version_id

    def rerun_comparison(self, rerun_run_id: str) -> dict:
        rerun = self.repository.get_run(rerun_run_id)
        if rerun is None:
            raise LookupError("run not found")
        if rerun.parent_run_id is None or rerun.rerun_case_id is None:
            raise ValueError("run is not a single-Case rerun")
        parent = self.repository.get_run(rerun.parent_run_id)
        if parent is None:
            raise LookupError("parent run not found")
        if rerun.status != "completed":
            raise ValueError("rerun is not completed")
        case_id = rerun.rerun_case_id
        case = next(item for item in rerun.snapshot.dataset.cases if item.id == case_id)
        original = {
            item.evaluator_id: item
            for item in self.repository.list_results(parent.id)
            if item.case_id == case_id
        }
        current = {
            item.evaluator_id: item
            for item in self.repository.list_results(rerun.id)
            if item.case_id == case_id
        }
        comparisons = []
        for evaluator_id in sorted(set(original) | set(current)):
            before, after = original.get(evaluator_id), current.get(evaluator_id)
            status = _comparison_status(before, after)
            comparisons.append({
                "evaluator_id": evaluator_id,
                "evaluator_name": (after or before).evaluator_name,
                "status": status,
                "before": _result_summary(before),
                "after": _result_summary(after),
            })
        counts = {
            status: sum(item["status"] == status for item in comparisons)
            for status in ("improved", "regressed", "unchanged", "incomparable")
        }
        overall = _overall_comparison(counts, len(comparisons))
        return {
            "root_run_id": rerun.root_run_id,
            "parent_run_id": parent.id,
            "rerun_run_id": rerun.id,
            "case_id": case_id,
            "case_name": case.name,
            "before_target_version": parent.snapshot.target.ref.external_version_id,
            "after_target_version": rerun.snapshot.target.ref.external_version_id,
            "overall": overall,
            "counts": counts,
            "evaluators": comparisons,
        }

    def trace(self, run_id: str, case_id: str):
        return self.repository.get_trace(run_id, case_id)

    def versions(self) -> list[dict]:
        return [
            {
                "id": reg.target_id,
                "label": reg.label,
                "adapter_type": reg.adapter_type,
                "endpoint": reg.invocation_config.get("endpoint"),
                "credential_ref": reg.credential_ref,
                "is_latest": reg.is_latest,
            }
            for reg in self._registry.values()
        ]

    def datasets(self) -> list[dict]:
        summaries = []
        for dataset in self.dataset_service.list_datasets():
            latest = self.repository.get_latest_dataset_version(dataset.id)
            draft = self.repository.get_dataset_draft(dataset.id)
            summaries.append({
                **dataset.model_dump(mode="json"),
                "version": latest.version if latest else None,
                "case_count": len(latest.cases) if latest else 0,
                "has_draft": draft is not None,
            })
        return summaries

    def evaluators(self) -> list[dict]:
        return [
            {
                "id": item.id,
                "name": item.name,
                "kind": item.kind,
                "version": item.version,
                "dimension": item.dimension,
                "metric": item.metric,
                "severity": item.severity,
                "evaluator_type": item.evaluator_type,
                "operator": getattr(item, "operator", None),
            }
            for item in EVALUATORS
        ]

    def validate_json_schema(self, json_schema, instance_mode: str = "structured") -> dict:
        issues = evaluator_validation.validate_json_schema(json_schema, instance_mode)
        if not issues:
            return {"valid": True}
        return {
            "valid": False,
            "errors": [issue.model_dump(mode="json", exclude_none=True) for issue in issues],
        }


def _result_summary(result) -> dict | None:
    if result is None:
        return None
    return {
        "outcome": result.outcome,
        "score": result.score,
        "reason": result.reason,
    }


def _comparison_status(before, after) -> str:
    if before is None or after is None:
        return "incomparable"
    excluded = {"error", "not_applicable"}
    if before.outcome in excluded or after.outcome in excluded:
        return "incomparable"
    if before.outcome == after.outcome and before.score == after.score:
        return "unchanged"
    if before.outcome in {"fail", "review"} and after.outcome == "pass":
        return "improved"
    if before.outcome == "pass" and after.outcome in {"fail", "review"}:
        return "regressed"
    if before.score is not None and after.score is not None:
        if after.score > before.score:
            return "improved"
        if after.score < before.score:
            return "regressed"
    return "unchanged"


def _overall_comparison(counts: dict[str, int], total: int) -> str:
    if counts["improved"] and counts["regressed"]:
        return "mixed"
    if counts["regressed"]:
        return "regressed"
    if counts["improved"]:
        return "improved"
    if total and counts["unchanged"] == total:
        return "unchanged"
    return "incomparable"
