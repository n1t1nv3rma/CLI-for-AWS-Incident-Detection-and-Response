"""EMR-specific alarm processing for create-alarms command.

This module handles filtering of non-monitorable EMR clusters from
alarm creation. Two categories are filtered:

1. **Terminated clusters** — clusters in TERMINATED,
   TERMINATED_WITH_ERRORS, or TERMINATING state are permanently
   dead and will never emit metrics again.
2. **Transient clusters** — clusters with AutoTerminate=True are
   ephemeral; each run gets a unique cluster ID, making
   ID-scoped alarms pointless.
"""

from typing import Any, Callable, Dict, FrozenSet, List, Optional, cast

from injector import inject

from aws_idr_customer_cli.core.interactive.ui import InteractiveUI
from aws_idr_customer_cli.data_accessors.emr_accessor import EmrAccessor
from aws_idr_customer_cli.services.file_cache.data import ResourceArn
from aws_idr_customer_cli.utils.log_handlers import CliLogger

# EMR states where the cluster is permanently shut down or shutting
# down.  Once a cluster reaches any of these states it will never
# produce metrics again and alarm creation is wasteful.
_TERMINAL_STATES: FrozenSet[str] = frozenset(
    {
        "TERMINATED",
        "TERMINATED_WITH_ERRORS",
        "TERMINATING",
    }
)


class EmrResourceProcessor:
    """Processor for EMR alarm configurations.

    Handles EMR-specific concerns:
    - Detecting terminated clusters via Status.State
    - Detecting transient vs persistent clusters via AutoTerminate
    - Skipping alarm creation for both categories
    """

    @inject
    def __init__(
        self,
        logger: CliLogger,
        ui: InteractiveUI,
        emr_accessor: Optional[EmrAccessor] = None,
    ) -> None:
        self.logger = logger
        self.ui = ui
        self.emr_accessor = emr_accessor

    def _extract_cluster_id(self, arn: str) -> str:
        """Extract cluster ID from an EMR ARN.

        EMR ARN format:
        arn:aws:elasticmapreduce:{region}:{account}:cluster/{id}
        """
        if "/" in arn:
            return arn.rsplit("/", 1)[-1]
        return arn.rsplit(":", 1)[-1]

    def _describe_cluster(self, resource: ResourceArn) -> Optional[Dict[str, Any]]:
        """Fetch cluster info via DescribeCluster.

        Returns the Cluster dict on success, or None if the accessor
        is unavailable or the API call fails (fail-open).
        """
        if self.emr_accessor is None:
            return None
        try:
            cluster_id = self._extract_cluster_id(resource.arn)
            return cast(
                Dict[str, Any],
                self.emr_accessor.describe_cluster(cluster_id, resource.region),
            )
        except Exception as e:
            self.logger.warning(
                f"Could not describe EMR cluster "
                f"{resource.arn}: {str(e)}. "
                f"Proceeding with alarm creation."
            )
            return None

    def _get_skip_reason(self, cluster_info: Optional[Dict[str, Any]]) -> Optional[str]:
        """Determine whether alarm creation should be skipped.

        Checks in order:
        1. Terminated state — cluster is dead.
        2. AutoTerminate — cluster is transient/ephemeral.

        Returns a human-readable reason string if the cluster should
        be skipped, or None to proceed with alarm creation.
        """
        if cluster_info is None:
            return None

        state = cluster_info.get("Status", {}).get("State", "")
        if state in _TERMINAL_STATES:
            return "terminated"

        if cluster_info.get("AutoTerminate", False):
            return "transient"

        return None

    def process_emr_resource(
        self,
        resource: ResourceArn,
        templates: List[Dict[str, Any]],
        create_alarm_config_fn: Callable[
            [Dict[str, Any], ResourceArn, bool],
            Optional[Dict[str, Any]],
        ],
        suppress_warnings: bool = False,
    ) -> List[Dict[str, Any]]:
        """Process an EMR resource, skipping non-monitorable clusters.

        A single DescribeCluster call is used to check both the
        cluster lifecycle state and the AutoTerminate flag.

        Args:
            resource: ResourceArn for the EMR cluster
            templates: Alarm templates for the EMR service
            create_alarm_config_fn: Callback to create a single alarm
            suppress_warnings: Whether to suppress warning messages

        Returns:
            List of alarm configuration dictionaries
        """
        cluster_info = self._describe_cluster(resource)
        skip_reason = self._get_skip_reason(cluster_info)

        if skip_reason is not None:
            cluster_id = self._extract_cluster_id(resource.arn)
            self.ui.display_warning(
                f"Skipping {skip_reason} EMR cluster "
                f"'{cluster_id}' - alarm creation is "
                f"only supported for running persistent "
                f"EMR clusters."
            )
            self.logger.warning(
                f"Skipping {skip_reason} EMR cluster " f"{resource.arn}: not supported"
            )
            return []

        if not templates:
            self.logger.warning("No templates found for service: emr")
            return []

        configurations: List[Dict[str, Any]] = []
        for template in templates:
            alarm_config = create_alarm_config_fn(template, resource, suppress_warnings)
            if alarm_config:
                configurations.append(alarm_config)

        return configurations
