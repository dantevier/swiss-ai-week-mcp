"""
System resources for the MCP Boilerplate server.
"""

import json
import platform
from datetime import datetime

import psutil

from ..config.settings import settings
from ..server import mcp
from ..utils.logger import setup_logger

logger = setup_logger("mcp_boilerplate.resources.system")


@mcp.resource("system://info")
def get_system_info() -> str:
    """Get basic system information."""
    try:
        info = {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "timestamp": datetime.now().isoformat(),
        }

        logger.debug("Retrieved system information")
        return json.dumps(info, indent=2)
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        raise


@mcp.resource("system://performance")
def get_system_performance() -> str:
    """Get current system performance metrics."""
    try:
        # CPU information
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()

        # Memory information
        memory = psutil.virtual_memory()

        # Disk information
        disk = psutil.disk_usage("/")

        performance = {
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count,
                "count_logical": psutil.cpu_count(logical=True),
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used,
                "free": memory.free,
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": (disk.used / disk.total) * 100,
            },
            "timestamp": datetime.now().isoformat(),
        }

        logger.debug("Retrieved system performance metrics")
        return json.dumps(performance, indent=2)
    except Exception as e:
        logger.error(f"Error getting performance info: {e}")
        raise


@mcp.resource("system://config")
def get_server_config() -> str:
    """Get current server configuration."""
    try:
        config = {
            "server_name": settings.server_name,
            "server_version": settings.server_version,
            "log_level": settings.log_level,
            "debug_mode": settings.enable_debug,
            "metrics_enabled": settings.enable_metrics,
            "max_request_size": settings.max_request_size,
            "request_timeout": settings.request_timeout,
            "timestamp": datetime.now().isoformat(),
        }

        logger.debug("Retrieved server configuration")
        return json.dumps(config, indent=2)
    except Exception as e:
        logger.error(f"Error getting server config: {e}")
        raise