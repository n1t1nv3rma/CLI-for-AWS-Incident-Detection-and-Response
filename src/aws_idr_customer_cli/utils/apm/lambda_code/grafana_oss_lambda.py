import json
import logging
import os
import re
from typing import Any, Dict
from uuid import uuid4

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_client = None


def _get_client() -> Any:
    """Lazy-initialize the EventBridge client to avoid import-time AWS calls."""
    global _client
    if _client is None:
        _client = boto3.client("events")
    return _client


DETAIL_TYPE = "ams.monitoring/generic-apm"  # Do not modify.
DETAIL_SOURCE = "GenericAPMEvent"  # Do not modify.
EVENTBUS_NAME_ENVIRONMENT_VALUE = "EnvEventBusName"  # Do not modify.
# Get incident path from environment variable for flexible updates
INCIDENT_PATH = os.environ.get("INCIDENT_PATH", 'alert["labels"]["alertname"]')


def _safe_extract_from_alert(alert: dict, path: str) -> str:
    """Safely extract a value from an alert dict using bracket notation path.

    Parses paths like 'alert["labels"]["alertname"]' without eval().
    """
    keys = re.findall(r'\["([^"]+)"\]', path)
    if not keys:
        raise ValueError(f"Invalid path format: {path}")
    result: Any = alert
    for key in keys:
        if not isinstance(result, dict):
            raise KeyError(f"Cannot access key '{key}' on non-dict")
        result = result[key]
    return str(result)


def lambda_handler(event: dict, context: object) -> dict:
    """
    Process Grafana OSS webhook alerts via API Gateway.

    Iterates over all alerts in the payload and sends one EventBridge event
    per alert, matching SNS lambda behavior for Grafana Cloud.
    """
    logger.info(event)
    session_id = str(uuid4())

    try:
        event_bus_name = os.environ[EVENTBUS_NAME_ENVIRONMENT_VALUE]
    except KeyError:
        msg = f"{session_id}: Missing environment variable {EVENTBUS_NAME_ENVIRONMENT_VALUE}"
        logger.error(msg)
        return _api_response(500, "Internal Server Error")

    try:
        body = (
            json.loads(event["body"]) if isinstance(event.get("body"), str) else event
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"{session_id}: Failed to parse request body: {e}")
        return _api_response(400, "Bad Request")

    alerts = body.get("alerts", [])
    if not alerts:
        logger.error(f"{session_id}: No 'alerts' field found in payload")
        return _api_response(400, "Bad Request: No alerts found")

    errors = []
    successes = []

    for alert in alerts:
        try:
            try:
                identifier = _safe_extract_from_alert(alert, INCIDENT_PATH)
            except Exception as e:
                logger.error(
                    f"{session_id}: Error extracting incident path "
                    f"'{INCIDENT_PATH}': {e}"
                )
                # Fallback to default path
                if "labels" in alert and "alertname" in alert["labels"]:
                    identifier = alert["labels"]["alertname"]
                else:
                    raise KeyError("Could not extract identifier from alert")

            detail = {
                "incident-detection-response-identifier": identifier,
                "original_message": body,
            }

            logger.info(f"{session_id}: Adding incident-detection-response-identifier")

            response = _get_client().put_events(
                Entries=[
                    {
                        "Detail": json.dumps(detail),
                        "DetailType": DETAIL_TYPE,  # Do not modify.
                        "Source": DETAIL_SOURCE,  # Do not modify.
                        "EventBusName": event_bus_name,  # Do not modify.
                    }
                ]
            )

            if response.get("FailedEntryCount", 0) > 0:
                logger.error(
                    f"{session_id}: EventBridge failed to publish event: {response}"
                )
                errors.append(identifier)
            else:
                successes.append(identifier)
                logger.info(
                    f"{session_id}: Successfully sent event to eventbus "
                    f"{event_bus_name}\n"
                    f"incident-detection-response-identifier:{identifier}\n"
                    f"DetailType:{DETAIL_TYPE}\nSource:{DETAIL_SOURCE}"
                )

        except KeyError as e:
            logger.error(f"{session_id}: Key error processing alert: {e}")
            errors.append(str(e))
            continue
        except Exception as e:
            logger.error(f"{session_id}: Unexpected error processing alert: {e}")
            errors.append(str(e))
            continue

    if errors and not successes:
        return _api_response(500, "Internal Server Error")
    if errors:
        return _api_response(
            207,
            f"Partial success: {len(successes)} succeeded, {len(errors)} failed",
        )

    return _api_response(200, "Success")


def _api_response(status_code: int, body: str) -> Dict[str, Any]:
    """Build API Gateway-compatible response."""
    return {
        "statusCode": status_code,
        "body": body,
        "headers": {"Content-Type": "application/json"},
    }
