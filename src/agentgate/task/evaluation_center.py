"""
评估中心对接模块。

负责与评估中心对接，上报评测结果。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class EvaluationCenterClient:
    """评估中心客户端"""

    def __init__(self, base_url: str = "", api_key: str = ""):
        self.base_url = base_url
        self.api_key = api_key
        self._enabled = bool(base_url)

    def is_enabled(self) -> bool:
        """检查是否启用"""
        return self._enabled

    def generate_report(
        self,
        task_id: str,
        run_id: str,
        snapshots: dict[str, str],
        summary: dict[str, Any],
        case_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        生成评估报告
        :param task_id: 任务ID
        :param run_id: 执行记录ID
        :param snapshots: 快照信息
        :param summary: 汇总信息
        :param case_results: 用例结果列表
        :return: 报告信息
        """
        if not self._enabled:
            logger.info("Evaluation center not enabled, skipping report generation")
            return {
                "report_id": f"RPT-{run_id[:8]}",
                "report_url": "",
                "status": "SKIPPED",
            }

        logger.info(f"Generating report for task {task_id}, run {run_id}")

        report_id = f"RPT-{task_id[:8]}-{run_id[:8]}"

        return {
            "report_id": report_id,
            "report_url": f"/api/v1/evaluation-center/reports/{report_id}",
            "status": "GENERATED",
        }

    def submit_report(
        self,
        task_id: str,
        run_id: str,
        report_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        提交评估报告
        :param task_id: 任务ID
        :param run_id: 执行记录ID
        :param report_data: 报告数据
        :return: 提交结果
        """
        if not self._enabled:
            logger.info("Evaluation center not enabled, skipping report submission")
            return {
                "success": False,
                "message": "Evaluation center not enabled",
            }

        logger.info(f"Submitting report for task {task_id}, run {run_id}")

        return {
            "success": True,
            "message": "Report submitted successfully",
        }


_evaluation_center_client: EvaluationCenterClient | None = None


def get_evaluation_center_client() -> EvaluationCenterClient:
    """获取评估中心客户端单例"""
    global _evaluation_center_client
    if _evaluation_center_client is None:
        _evaluation_center_client = EvaluationCenterClient()
    return _evaluation_center_client


def set_evaluation_center_client(client: EvaluationCenterClient) -> None:
    """设置评估中心客户端"""
    global _evaluation_center_client
    _evaluation_center_client = client
