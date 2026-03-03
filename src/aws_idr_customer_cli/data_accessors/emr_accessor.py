from typing import Any, Callable, Dict, cast

from botocore.exceptions import ClientError
from injector import inject
from retry import retry

from aws_idr_customer_cli.data_accessors.base_accessor import BaseAccessor
from aws_idr_customer_cli.utils.constants import BotoServiceName
from aws_idr_customer_cli.utils.log_handlers import CliLogger


class EmrAccessor(BaseAccessor):
    """Data accessor for EMR operations with multi-region support."""

    MAX_RETRIES = 5

    @inject
    def __init__(
        self, logger: CliLogger, client_factory: Callable[[str, str], Any]
    ) -> None:
        super().__init__(logger, "EMR API")
        self.create_client = client_factory

    def _get_client(self, region: str) -> Any:
        """Get EMR client for specified region using cached factory."""
        return self.create_client(BotoServiceName.EMR, region)

    @retry(exceptions=ClientError, tries=MAX_RETRIES, delay=1, backoff=2, logger=None)
    def describe_cluster(self, cluster_id: str, region: str) -> Dict[str, Any]:
        """Describe an EMR cluster.

        Args:
            cluster_id: The EMR cluster identifier (e.g. j-XXXXXXXXXXXXX)
            region: AWS region of the cluster

        Returns:
            Cluster info dictionary from the DescribeCluster response
        """
        try:
            client = self._get_client(region)
            response = client.describe_cluster(ClusterId=cluster_id)
            return cast(Dict[str, Any], response.get("Cluster", {}))
        except ClientError as exception:
            self._handle_error(exception, "describe_cluster")
            raise
        except Exception as exception:
            self.logger.error(
                f"Unexpected error in describe_cluster: " f"{str(exception)}"
            )
            raise
