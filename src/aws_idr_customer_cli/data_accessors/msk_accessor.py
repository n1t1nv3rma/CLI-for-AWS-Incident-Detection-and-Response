from typing import Any, Callable, Dict, List, cast

from botocore.exceptions import ClientError
from injector import inject
from retry import retry

from aws_idr_customer_cli.data_accessors.base_accessor import BaseAccessor
from aws_idr_customer_cli.utils.constants import BotoServiceName
from aws_idr_customer_cli.utils.log_handlers import CliLogger


class MskAccessor(BaseAccessor):
    """Data accessor for MSK operations with multi-region support."""

    MAX_RETRIES = 5

    @inject
    def __init__(
        self, logger: CliLogger, client_factory: Callable[[str, str], Any]
    ) -> None:
        super().__init__(logger, "MSK API")
        self.create_client = client_factory

    def _get_client(self, region: str) -> Any:
        """Get MSK client for specified region using cached factory."""
        return self.create_client(BotoServiceName.KAFKA, region)

    @retry(exceptions=ClientError, tries=MAX_RETRIES, delay=1, backoff=2, logger=None)
    def list_nodes(self, cluster_arn: str, region: str) -> List[str]:
        """List broker node IDs for an MSK cluster."""
        try:
            client = self._get_client(region)
            response = client.list_nodes(ClusterArn=cluster_arn)
            return [
                str(node.get("BrokerNodeInfo", {}).get("BrokerId", ""))
                for node in response.get("NodeInfoList", [])
            ]
        except ClientError as exception:
            self._handle_error(exception, "list_nodes")
            raise
        except Exception as exception:
            self.logger.error(f"Unexpected error in list_nodes: {str(exception)}")
            raise

    @retry(exceptions=ClientError, tries=MAX_RETRIES, delay=1, backoff=2, logger=None)
    def describe_cluster(self, cluster_arn: str, region: str) -> Dict[str, Any]:
        """Describe an MSK cluster."""
        try:
            client = self._get_client(region)
            response = client.describe_cluster_v2(ClusterArn=cluster_arn)
            return cast(Dict[str, Any], response.get("ClusterInfo", {}))
        except ClientError as exception:
            self._handle_error(exception, "describe_cluster")
            raise
        except Exception as exception:
            self.logger.error(f"Unexpected error in describe_cluster: {str(exception)}")
            raise
