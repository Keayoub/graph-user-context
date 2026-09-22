"""Optional Azure Monitor setup with sensitive payload collection disabled."""

from __future__ import annotations

import logging
from importlib import import_module

from graph_context.config import Settings

logger = logging.getLogger(__name__)


def configure_telemetry(settings: Settings) -> None:
    connection_string = settings.appinsights_connection_string
    if not connection_string:
        return
    try:
        configure_azure_monitor = import_module(
            "azure.monitor.opentelemetry"
        ).configure_azure_monitor

        configure_azure_monitor(
            connection_string=connection_string.get_secret_value(),
            enable_live_metrics=False,
            disable_offline_storage=True,
        )
    except ImportError:
        logger.warning(
            "Application Insights configured but azure-monitor-opentelemetry is unavailable"
        )
