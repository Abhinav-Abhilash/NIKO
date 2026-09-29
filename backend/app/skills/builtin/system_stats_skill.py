import asyncio
import os
from typing import Any

import psutil

from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult


class SystemStatsSkill(BaseSkill):
    """Provides real-time host performance and resource utilization metrics."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="system_stats",
            description="Inspect host system performance and resource utilization (CPU, RAM, Disk, Battery).",
            default_tier="SAFE",
            default_autonomy="auto",
            timeout_seconds=10,
            parameters_schema={
                "type": "object",
                "properties": {
                    "detail": {
                        "type": "boolean",
                        "description": "Whether to return detailed disk partitions and per-core CPU breakdown. Default false.",
                    }
                },
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        detail = bool(arguments.get("detail", False))

        def _gather_metrics() -> dict[str, Any]:
            cpu_pct = psutil.cpu_percent(interval=0.1)
            vm = psutil.virtual_memory()

            root_path = "C:\\" if os.name == "nt" else "/"
            try:
                disk = psutil.disk_usage(root_path)
            except Exception:
                disk = psutil.disk_usage("/")

            battery_stat = psutil.sensors_battery()
            battery_data: dict[str, Any] | None = None
            if battery_stat:
                battery_data = {
                    "percent": battery_stat.percent,
                    "power_plugged": battery_stat.power_plugged,
                    "secsleft": battery_stat.secsleft if battery_stat.secsleft != psutil.BATTERY_TIME_UNLIMITED else None,
                }

            metrics: dict[str, Any] = {
                "cpu": {
                    "percent": cpu_pct,
                    "logical_cores": psutil.cpu_count(logical=True),
                    "physical_cores": psutil.cpu_count(logical=False),
                },
                "ram": {
                    "total_mb": round(vm.total / (1024 * 1024), 1),
                    "used_mb": round(vm.used / (1024 * 1024), 1),
                    "available_mb": round(vm.available / (1024 * 1024), 1),
                    "percent": vm.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent": disk.percent,
                },
                "battery": battery_data,
            }

            if detail:
                metrics["cpu"]["per_cpu_percent"] = psutil.cpu_percent(interval=0.0, percpu=True)
                partitions = []
                for part in psutil.disk_partitions(all=False):
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        partitions.append(
                            {
                                "device": part.device,
                                "mountpoint": part.mountpoint,
                                "fstype": part.fstype,
                                "total_gb": round(usage.total / (1024**3), 2),
                                "free_gb": round(usage.free / (1024**3), 2),
                                "percent": usage.percent,
                            }
                        )
                    except (PermissionError, OSError):
                        continue
                metrics["disk"]["partitions"] = partitions

            return metrics

        metrics_result = await asyncio.to_thread(_gather_metrics)
        return SkillResult(success=True, data=metrics_result)
