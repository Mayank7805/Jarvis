"""
skills/system_info.py — System Information Skill

Reports battery, RAM, CPU, and disk usage using the ``psutil`` library.

Dependencies:
    pip install psutil
"""

import psutil

from skills.base_skill import BaseSkill


class SystemInfoSkill(BaseSkill):
    """Reports real-time system metrics: battery, RAM, CPU, disk."""

    @property
    def name(self) -> str:
        return "System Info"

    @property
    def keywords(self) -> list[str]:
        return [
            "battery", "ram", "memory", "cpu",
            "disk", "storage", "system info", "performance",
        ]

    def execute(self, query: str) -> str:
        """Route to the appropriate system metric."""
        q = query.lower()

        if "battery" in q:
            return self._get_battery()
        if "ram" in q or "memory" in q:
            return self._get_ram()
        if "cpu" in q or "processor" in q:
            return self._get_cpu()
        if "disk" in q or "storage" in q:
            return self._get_disk()
        if "system info" in q or "performance" in q:
            return self._get_all()

        # Fallback: return everything
        return self._get_all()

    # ── Metric Collectors ──────────────────────

    @staticmethod
    def _get_battery() -> str:
        """Report battery percentage and charging status."""
        battery = psutil.sensors_battery()
        if battery is None:
            return "No battery detected. This might be a desktop PC."

        percent = battery.percent
        plugged = "charging" if battery.power_plugged else "not charging"
        return f"Battery is at {percent} percent, {plugged}."

    @staticmethod
    def _get_ram() -> str:
        """Report RAM usage in GB."""
        mem = psutil.virtual_memory()
        used_gb = round(mem.used / (1024 ** 3), 1)
        total_gb = round(mem.total / (1024 ** 3), 1)
        return (
            f"RAM usage is {mem.percent} percent. "
            f"{used_gb} GB used out of {total_gb} GB total."
        )

    @staticmethod
    def _get_cpu() -> str:
        """Report current CPU utilization (1-second sample)."""
        percent = psutil.cpu_percent(interval=1)
        cores = psutil.cpu_count(logical=True)
        return f"CPU usage is {percent} percent across {cores} logical cores."

    @staticmethod
    def _get_disk() -> str:
        """Report primary disk (C:) usage."""
        disk = psutil.disk_usage("C:\\")
        free_gb = round(disk.free / (1024 ** 3), 1)
        total_gb = round(disk.total / (1024 ** 3), 1)
        return (
            f"Disk usage is {disk.percent} percent. "
            f"{free_gb} GB free out of {total_gb} GB total."
        )

    def _get_all(self) -> str:
        """Combine all metrics into a single summary."""
        parts = [
            self._get_cpu(),
            self._get_ram(),
            self._get_disk(),
        ]
        # Include battery only if present
        battery = psutil.sensors_battery()
        if battery is not None:
            parts.insert(0, self._get_battery())

        return " ".join(parts)
