"""Data accessor for Amazon OpenSearch Service operations."""

from typing import Any, Callable

from botocore.exceptions import ClientError
from injector import inject
from retry import retry

from aws_idr_customer_cli.data_accessors.base_accessor import BaseAccessor
from aws_idr_customer_cli.utils.constants import BotoServiceName
from aws_idr_customer_cli.utils.log_handlers import CliLogger


class OpenSearchAccessor(BaseAccessor):
    """Data accessor for OpenSearch operations with multi-region support.

    Provides methods to query OpenSearch domain configuration.
    """

    MAX_RETRIES = 5

    @inject
    def __init__(
        self, logger: CliLogger, client_factory: Callable[[str, str], Any]
    ) -> None:
        """Initialize OpenSearchAccessor with logger and client factory.

        Args:
            logger: CLI logger instance for logging operations
            client_factory: Factory function to create boto3 clients
        """
        super().__init__(logger, "OpenSearch API")
        self.create_client = client_factory

    def _get_client(self, region: str) -> Any:
        """Get OpenSearch client for specified region using cached factory.

        Args:
            region: AWS region name

        Returns:
            Boto3 OpenSearch client
        """
        return self.create_client(BotoServiceName.OPENSEARCH, region)

    @retry(exceptions=ClientError, tries=MAX_RETRIES, delay=1, backoff=2, logger=None)
    def describe_domain(self, domain_name: str, region: str) -> dict[str, Any]:
        """Describe OpenSearch domain to get configuration details.

        Args:
            domain_name: Name of the OpenSearch domain
            region: AWS region where the domain is located

        Returns:
            Dictionary containing domain status information including
            EBSOptions, ClusterConfig, and other domain settings

        Raises:
            ValueError: If domain is not found or invalid parameters
            PermissionError: If access to the domain is denied
            ClientError: For other AWS API errors
        """
        try:
            client = self._get_client(region)
            response = client.describe_domain(DomainName=domain_name)
            domain_status: dict[str, Any] = response.get("DomainStatus", {})
            return domain_status
        except ClientError as exception:
            self._handle_error(exception, "describe_domain")
            raise
        except Exception as exception:
            self.logger.error(f"Unexpected error in describe_domain: {str(exception)}")
            raise
