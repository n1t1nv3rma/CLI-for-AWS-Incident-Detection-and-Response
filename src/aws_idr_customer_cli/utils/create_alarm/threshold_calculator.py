"""Calculates dynamic alarm thresholds for service-specific metrics."""

from typing import Optional

from injector import inject

from aws_idr_customer_cli.data_accessors.opensearch_accessor import OpenSearchAccessor
from aws_idr_customer_cli.utils.log_handlers import CliLogger

# Default percentage for FreeStorageSpace threshold calculation
DEFAULT_FREE_STORAGE_PERCENTAGE = 0.25  # 25% of total storage


class ThresholdCalculator:
    """Calculates dynamic thresholds using service accessors.

    Responsible for querying resource configurations and computing
    appropriate alarm threshold values based on resource capacity.
    """

    @inject
    def __init__(
        self,
        logger: CliLogger,
        opensearch_accessor: OpenSearchAccessor,
    ) -> None:
        """Initialize ThresholdCalculator with logger and service accessors.

        Args:
            logger: CLI logger instance for logging operations
            opensearch_accessor: Accessor for OpenSearch API operations
        """
        self.logger = logger
        self.opensearch_accessor = opensearch_accessor

    def get_opensearch_free_storage_threshold(
        self,
        domain_name: str,
        region: str,
        percentage: float = DEFAULT_FREE_STORAGE_PERCENTAGE,
    ) -> Optional[int]:
        """Calculate FreeStorageSpace alarm threshold based on domain's EBS volume size.

        The FreeStorageSpace CloudWatch metric reports available storage in MiB.
        This method calculates a threshold at the specified percentage of total
        storage capacity.

        Args:
            domain_name: Name of the OpenSearch domain
            region: AWS region where the domain is located
            percentage: Threshold percentage (0.0-1.0). Default is 0.25 (25%)

        Returns:
            Threshold value in MiB, or None if unable to calculate
            (e.g., EBS not enabled or API error)

        Example:
            For a domain with 100 GiB EBS volume and 25% threshold:
            - threshold = 100 * 1024 * 0.25 = 25,600 MiB
        """
        try:
            domain_status = self.opensearch_accessor.describe_domain(
                domain_name, region
            )
            ebs_options = domain_status.get("EBSOptions", {})

            if not ebs_options.get("EBSEnabled", False):
                self.logger.warning(
                    f"Domain {domain_name} does not have EBS enabled (uses instance "
                    f"storage)"
                )
                return None

            volume_size: Optional[int] = ebs_options.get("VolumeSize")
            if volume_size is None:
                self.logger.warning(
                    f"Cannot calculate FreeStorageSpace threshold for domain "
                    f"{domain_name}: EBS volume size not available"
                )
                return None

            # Convert GiB to MiB and apply percentage
            # FreeStorageSpace metric is reported in MiB
            threshold_mib = int(volume_size * 1024 * percentage)

            self.logger.info(
                f"Calculated FreeStorageSpace threshold for domain {domain_name}: "
                f"{threshold_mib} MiB ({percentage * 100:.0f}% of {volume_size} GiB)"
            )

            return threshold_mib

        except Exception as e:
            self.logger.error(
                f"Failed to calculate FreeStorageSpace threshold for domain "
                f"{domain_name}: {str(e)}"
            )
            return None
