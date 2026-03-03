"""MSK-specific alarm processing for create-alarms command.

This module handles the specialized logic for Amazon MSK (Managed Streaming
for Apache Kafka) clusters, including broker discovery, per-broker template
expansion, Serverless cluster detection, and Standard/Express broker type
filtering.
"""

import copy
from typing import Any, Callable, Dict, List, Optional, Tuple

from injector import inject

from aws_idr_customer_cli.core.interactive.ui import InteractiveUI
from aws_idr_customer_cli.data_accessors.msk_accessor import MskAccessor
from aws_idr_customer_cli.services.file_cache.data import ResourceArn
from aws_idr_customer_cli.utils.constants import MskBrokerType
from aws_idr_customer_cli.utils.log_handlers import CliLogger


class MskResourceProcessor:
    """Processor for MSK alarm configurations.

    Handles MSK-specific concerns:
    - Detecting Serverless vs Provisioned clusters
    - Determining broker type (STANDARD vs EXPRESS)
    - Filtering templates by broker type
    - Discovering broker IDs via ListNodes
    - Expanding per-broker templates (${broker_id}) into N alarms
    - Caching cluster info and broker IDs per cluster ARN
    """

    @inject
    def __init__(
        self,
        logger: CliLogger,
        ui: InteractiveUI,
        msk_accessor: Optional[MskAccessor] = None,
    ) -> None:
        self.logger = logger
        self.ui = ui
        self.msk_accessor = msk_accessor
        self._broker_cache: Dict[str, List[str]] = {}
        self._cluster_info_cache: Dict[str, Optional[Dict[str, Any]]] = {}

    def _get_cluster_info(self, resource: ResourceArn) -> Optional[Dict[str, Any]]:
        """Retrieve and cache cluster info from describe_cluster_v2.

        Returns cached result on subsequent calls for the same ARN.
        Returns None on API errors so callers can skip the cluster.
        """
        if resource.arn in self._cluster_info_cache:
            return self._cluster_info_cache[resource.arn]

        if self.msk_accessor is None:
            self._cluster_info_cache[resource.arn] = None
            return None

        try:
            cluster_info: Dict[str, Any] = self.msk_accessor.describe_cluster(
                resource.arn, resource.region
            )
            self._cluster_info_cache[resource.arn] = cluster_info
            return cluster_info
        except Exception as e:
            self.logger.warning(
                f"Could not determine MSK cluster type for "
                f"{resource.arn}: {str(e)}."
            )
            self._cluster_info_cache[resource.arn] = None
            return None

    def _get_cluster_type_and_broker_type(
        self, resource: ResourceArn
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract cluster type and broker type from cluster info.

        Returns:
            Tuple of (cluster_type, broker_type).
            Returns (None, None) when the API call failed.
        """
        cluster_info = self._get_cluster_info(resource)
        if cluster_info is None:
            return None, None
        cluster_type: str = cluster_info.get("ClusterType", "")
        provisioned = cluster_info.get("Provisioned", {})
        instance_type: str = provisioned.get("BrokerNodeGroupInfo", {}).get(
            "InstanceType", ""
        )
        if instance_type.startswith("express."):
            broker_type = MskBrokerType.EXPRESS.value
        else:
            broker_type = MskBrokerType.STANDARD.value
        return cluster_type, broker_type

    def is_msk_serverless(self, resource: ResourceArn) -> bool:
        """Check if an MSK cluster is Serverless.

        Returns True if the cluster is SERVERLESS, False otherwise.
        Returns False when the API call fails (cluster_type is None).
        """
        cluster_type, _ = self._get_cluster_type_and_broker_type(resource)
        return cluster_type == "SERVERLESS"

    @staticmethod
    def filter_templates_by_broker_type(
        templates: List[Dict[str, Any]],
        broker_type: str,
    ) -> List[Dict[str, Any]]:
        """Filter templates to those matching the cluster's broker type.

        Templates with a ``broker_type`` field are included only when it
        matches.  Templates without the field are included unconditionally
        for forward compatibility.
        """
        return [
            t for t in templates if t.get("broker_type", broker_type) == broker_type
        ]

    def process_msk_resource(
        self,
        resource: ResourceArn,
        templates: List[Dict[str, Any]],
        create_alarm_config_fn: Callable[
            [Dict[str, Any], ResourceArn, bool],
            Optional[Dict[str, Any]],
        ],
        suppress_warnings: bool = False,
    ) -> List[Dict[str, Any]]:
        """Process an MSK resource, expanding per-broker templates.

        Processing pipeline:
        1. Determine cluster type (Serverless → skip)
        2. Determine broker type (STANDARD/EXPRESS)
        3. Filter templates by broker type
        4. Discover broker IDs
        5. Classify templates: cluster-only vs per-broker
        6. Create alarm configurations

        Args:
            resource: ResourceArn for the MSK cluster
            templates: Alarm templates for the MSK service
            create_alarm_config_fn: Callback to create a single alarm config
            suppress_warnings: Whether to suppress warning messages

        Returns:
            List of alarm configuration dictionaries
        """
        cluster_type, broker_type = self._get_cluster_type_and_broker_type(resource)

        if cluster_type is None or broker_type is None:
            cluster_name = (
                resource.arn.split("/")[-2] if "/" in resource.arn else resource.arn
            )
            self.ui.display_warning(
                f"Skipping MSK cluster '{cluster_name}' - "
                f"unable to determine cluster type. "
                f"Verify IAM permissions for "
                f"kafka:DescribeClusterV2."
            )
            self.logger.warning(
                f"Skipping MSK cluster {resource.arn}: " f"describe_cluster_v2 failed"
            )
            return []

        if cluster_type == "SERVERLESS":
            cluster_name = (
                resource.arn.split("/")[-2] if "/" in resource.arn else resource.arn
            )
            self.ui.display_warning(
                f"Skipping MSK Serverless cluster "
                f"'{cluster_name}' - alarm creation is "
                f"only supported for MSK Provisioned "
                f"clusters."
            )
            self.logger.warning(
                f"Skipping MSK Serverless cluster " f"{resource.arn}: not supported"
            )
            return []

        if not templates:
            self.logger.warning("No templates found for service: msk")
            return []

        # Filter templates by broker type
        filtered = self.filter_templates_by_broker_type(templates, broker_type)
        self.logger.info(
            f"MSK broker type '{broker_type}': "
            f"{len(filtered)}/{len(templates)} templates applicable"
        )

        if not filtered:
            self.logger.warning(
                f"No templates match broker type " f"'{broker_type}' for {resource.arn}"
            )
            return []

        broker_ids = self._discover_broker_ids(resource)

        # Classify templates into cluster-only vs per-broker
        cluster_templates: List[Dict[str, Any]] = []
        broker_templates: List[Dict[str, Any]] = []
        for template in filtered:
            if "${broker_id}" in str(template.get("configuration", {})):
                broker_templates.append(template)
            else:
                cluster_templates.append(template)

        configurations: List[Dict[str, Any]] = []

        for template in cluster_templates:
            alarm_config = create_alarm_config_fn(template, resource, suppress_warnings)
            if alarm_config:
                configurations.append(alarm_config)

        for template in broker_templates:
            for broker_id in broker_ids:
                resolved = self.resolve_broker_id_in_template(template, broker_id)
                alarm_config = create_alarm_config_fn(
                    resolved, resource, suppress_warnings
                )
                if alarm_config:
                    configurations.append(alarm_config)

        return configurations

    def _discover_broker_ids(self, resource: ResourceArn) -> List[str]:
        """Discover broker IDs for an MSK cluster with caching."""
        if resource.arn in self._broker_cache:
            return self._broker_cache[resource.arn]

        broker_ids: List[str] = []
        try:
            if self.msk_accessor is None:
                raise RuntimeError("MskAccessor not available")
            broker_ids = (
                self.msk_accessor.list_nodes(resource.arn, resource.region) or []
            )
        except Exception:
            self.logger.warning(
                f"Exception discovering brokers for MSK cluster " f"{resource.arn}"
            )

        self._broker_cache[resource.arn] = broker_ids

        if broker_ids:
            self.logger.info(
                f"Discovered {len(broker_ids)} brokers for "
                f"MSK cluster: {broker_ids}"
            )
        else:
            self.logger.warning(
                f"Could not discover brokers for MSK cluster "
                f"{resource.arn}. Creating cluster-only alarms."
            )

        return broker_ids

    @staticmethod
    def resolve_broker_id_in_template(
        template: Dict[str, Any], broker_id: str
    ) -> Dict[str, Any]:
        """Replace all ${broker_id} occurrences in a template.

        Args:
            template: Alarm template dict (deep-copied internally)
            broker_id: Broker ID string to substitute

        Returns:
            New template dict with ${broker_id} replaced
        """
        resolved = copy.deepcopy(template)
        config = resolved.get("configuration", {})

        if isinstance(config.get("AlarmName"), str):
            config["AlarmName"] = config["AlarmName"].replace("${broker_id}", broker_id)

        for dim in config.get("Dimensions", []):
            if isinstance(dim, dict) and isinstance(dim.get("Value"), str):
                dim["Value"] = dim["Value"].replace("${broker_id}", broker_id)

        for metric in config.get("Metrics", []):
            if not isinstance(metric, dict):
                continue
            metric_stat = metric.get("MetricStat", {})
            if isinstance(metric_stat, dict):
                metric_obj = metric_stat.get("Metric", {})
                if isinstance(metric_obj, dict):
                    for dim in metric_obj.get("Dimensions", []):
                        if isinstance(dim, dict) and isinstance(dim.get("Value"), str):
                            dim["Value"] = dim["Value"].replace(
                                "${broker_id}", broker_id
                            )

        return resolved
