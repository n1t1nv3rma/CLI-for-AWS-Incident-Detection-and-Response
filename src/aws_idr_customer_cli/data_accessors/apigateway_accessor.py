from typing import Any, Callable, Dict, Optional

from injector import inject

from aws_idr_customer_cli.data_accessors.base_accessor import BaseAccessor
from aws_idr_customer_cli.utils.log_handlers import CliLogger


class ApiGatewayAccessor(BaseAccessor):

    @inject
    def __init__(
        self, logger: CliLogger, client_factory: Callable[[str, str], Any]
    ) -> None:
        super().__init__(logger, "API Gateway API")
        self.create_client = client_factory

    def get_rest_api_name(self, api_id: str, region: str) -> Optional[str]:
        try:
            self.logger.debug(
                f"Calling API Gateway GetRestApi API for API ID: {api_id} in region: {region}"
            )
            client = self.create_client("apigateway", region)
            response = client.get_rest_api(restApiId=api_id)
            name = response.get("name")

            if name is not None:
                return str(name)
            else:
                self.logger.warning(
                    f"API Gateway GetRestApi returned no 'name' field for API ID: {api_id}"
                )
                return None
        except Exception as e:
            self.logger.warning(
                f"Failed to call API Gateway GetRestApi for "
                f"API ID {api_id} in region {region}: {str(e)}"
            )
            return None

    def get_http_api_details(
        self, api_id: str, region: str
    ) -> Optional[Dict[str, str]]:
        """Get HTTP/WebSocket API details using API Gateway V2.

        This method calls apigatewayv2:GetApi to retrieve details about HTTP APIs
        and WebSocket APIs. Both API types share the same ARN pattern (apis/)
        but have different CloudWatch metrics, so the protocol type must be
        determined to select the correct alarm templates.

        Args:
            api_id: The API identifier (from ARN: arn:aws:apigateway:{region}::/apis/{api_id})
            region: AWS region where the API is deployed

        Returns:
            Dictionary containing:
                - api_id: The API identifier
                - name: Human-readable API name
                - protocol_type: "HTTP" or "WEBSOCKET"
            Returns None if the API cannot be found or an error occurs.
        """
        try:
            self.logger.debug(
                f"Calling API Gateway V2 GetApi for API ID: {api_id} in region: {region}"
            )
            client = self.create_client("apigatewayv2", region)
            response = client.get_api(ApiId=api_id)

            name = response.get("Name")
            protocol_type = response.get("ProtocolType")

            if protocol_type is None:
                self.logger.warning(
                    f"API Gateway V2 GetApi returned no 'ProtocolType' for API ID: {api_id}"
                )
                return None

            return {
                "api_id": api_id,
                "name": str(name) if name else api_id,
                "protocol_type": str(protocol_type),
            }
        except Exception as e:
            self.logger.warning(
                f"Failed to call API Gateway V2 GetApi for "
                f"API ID {api_id} in region {region}: {str(e)}"
            )
            return None
