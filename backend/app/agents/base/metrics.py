import os
from typing import Dict, Any, List

try:
    import psutil
except ImportError:
    psutil = None


class AgentMetricsCollector:
    """
    Collects execution metrics: execution times, memory, CPU, retry count, rates, etc.
    Exposes metrics in a Prometheus-ready format.
    """

    _usage_counts: Dict[str, int] = {}
    _execution_times: Dict[str, List[float]] = {}
    _retry_counts: Dict[str, int] = {}
    _success_counts: Dict[str, int] = {}
    _failure_counts: Dict[str, int] = {}

    @classmethod
    def reset(cls):
        """Clears all counters (helper for test cleanliness)."""
        cls._usage_counts = {}
        cls._execution_times = {}
        cls._retry_counts = {}
        cls._success_counts = {}
        cls._failure_counts = {}

    @classmethod
    def record_run(
        cls, agent_name: str, execution_time_ms: float, success: bool, retries: int = 0
    ):
        if agent_name not in cls._usage_counts:
            cls._usage_counts[agent_name] = 0
            cls._execution_times[agent_name] = []
            cls._retry_counts[agent_name] = 0
            cls._success_counts[agent_name] = 0
            cls._failure_counts[agent_name] = 0

        cls._usage_counts[agent_name] += 1
        cls._execution_times[agent_name].append(execution_time_ms)
        cls._retry_counts[agent_name] += retries
        if success:
            cls._success_counts[agent_name] += 1
        else:
            cls._failure_counts[agent_name] += 1

    @classmethod
    def get_system_metrics(cls) -> Dict[str, float]:
        """Gets CPU and Memory utilization of the current process with safe fallbacks if psutil is absent."""
        if psutil is not None:
            try:
                process = psutil.Process(os.getpid())
                mem_info = process.memory_info()
                cpu_pct = process.cpu_percent(interval=None)
                return {
                    "cpu_usage_percent": float(cpu_pct),
                    "memory_rss_bytes": float(mem_info.rss),
                    "memory_vms_bytes": float(mem_info.vms),
                }
            except Exception:
                pass

        # Fallbacks
        return {
            "cpu_usage_percent": 0.0,
            "memory_rss_bytes": 0.0,
            "memory_vms_bytes": 0.0,
        }

    @classmethod
    def get_agent_metrics(cls, agent_name: str) -> Dict[str, Any]:
        if agent_name not in cls._usage_counts:
            return {}

        times = cls._execution_times[agent_name]
        avg_time = sum(times) / len(times) if times else 0.0
        successes = cls._success_counts[agent_name]
        failures = cls._failure_counts[agent_name]
        total = successes + failures
        success_rate = successes / total if total > 0 else 0.0
        failure_rate = failures / total if total > 0 else 0.0

        return {
            "usage_count": cls._usage_counts[agent_name],
            "average_execution_time_ms": round(avg_time, 2),
            "retry_count": cls._retry_counts[agent_name],
            "success_rate": round(success_rate, 4),
            "failure_rate": round(failure_rate, 4),
        }

    @classmethod
    def to_prometheus_format(cls) -> str:
        """Outputs collected metrics in standard Prometheus exposition format."""
        lines = []
        # Expose agent usage count
        lines.append(
            "# HELP agent_usage_total Total number of times an agent has executed"
        )
        lines.append("# TYPE agent_usage_total counter")
        for agent, count in cls._usage_counts.items():
            lines.append(f'agent_usage_total{{agent="{agent}"}} {count}')

        # Expose average execution times
        lines.append(
            "# HELP agent_execution_time_average_ms Average response time in milliseconds"
        )
        lines.append("# TYPE agent_execution_time_average_ms gauge")
        for agent, times in cls._execution_times.items():
            avg = sum(times) / len(times) if times else 0.0
            lines.append(
                f'agent_execution_time_average_ms{{agent="{agent}"}} {round(avg, 2)}'
            )

        # Expose retry count
        lines.append(
            "# HELP agent_retries_total Total retry counts for agent executions"
        )
        lines.append("# TYPE agent_retries_total counter")
        for agent, retries in cls._retry_counts.items():
            lines.append(f'agent_retries_total{{agent="{agent}"}} {retries}')

        # Expose process metrics
        sys = cls.get_system_metrics()
        lines.append(
            "# HELP process_cpu_usage_ratio CPU usage ratio of the agent process"
        )
        lines.append("# TYPE process_cpu_usage_ratio gauge")
        lines.append(f"process_cpu_usage_ratio {sys['cpu_usage_percent'] / 100.0}")

        lines.append("# HELP process_memory_rss_bytes RSS Memory footprint in bytes")
        lines.append("# TYPE process_memory_rss_bytes gauge")
        lines.append(f"process_memory_rss_bytes {sys['memory_rss_bytes']}")

        return "\n".join(lines)
