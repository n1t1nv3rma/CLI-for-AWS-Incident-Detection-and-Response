"""OpenSearch-specific alarm processing for create-alarms command.

This module handles the specialized logic for Amazon OpenSearch Service,
including dynamic threshold calculation for FreeStorageSpace alarms based
on the domain's actual EBS volume size.
"""

import copy
from typing import Any, Dict, List, Optional

from arnparse import arnparse
from injector import inject

from aws_idr_customer_cli.services.file_cache.data import ResourceArn
from aws_idr_customer_cli.utils.create_alarm.threshold_calculator import (
    ThresholdCalculator,
)
from aws_idr_customer_cli.utils.log_handlers import CliLogger


class OpenSearchResourceProcessor:
    """Processor for OpenSearch alarm template enrichment.

    Handles OpenSearch-specific concerns:
    - Extracting domain names from OpenSearch ARNs
    - Calculating dynamic FreeStorageSpace thresholds based on EBS volume size
    - Filtering out FreeStorageSpace alarms when threshold cannot be determined
    """

    @inject
    def __init__(
        self,
        logger: CliLogger,
        threshold_calculator: ThresholdCalculator,
    ) -> None:
        """Initialize OpenSearchResourceProcessor.

        Args:
            logger: CLI logger instance
            threshold_calculator: Calculator for dynamic alarm thresholds
        """
        self.logger = logger
        self.threshold_calculator = threshold_calculator

    def enrich_templates(
        self,
        templates: List[Dict[str, Any]],
        resource: ResourceArn,
    ) -> List[Dict[str, Any]]:
        """Enrich OpenSearch templates with dynamic thresholds.

        For FreeStorageSpace alarms, queries the OpenSearch domain
        configuration to calculate an appropriate threshold based on
        the actual EBS volume size (25% of total storage).

        Args:
            templates: List of alarm templates for OpenSearch
            resource: ResourceArn for the OpenSearch domain

        Returns:
            List of templates with FreeStorageSpace threshold populated
        """
        domain_name = self.extract_domain_name(resource.arn)
        if not domain_name:
            self.logger.warning(
                f"Could not extract domain name from ARN: " f"{resource.arn}"
            )
            return templates

        free_storage_threshold = (
            self.threshold_calculator.get_opensearch_free_storage_threshold(
                domain_name, resource.region
            )
        )

        if free_storage_threshold is None:
            self.logger.warning(
                f"Could not calculate FreeStorageSpace threshold "
                f"for domain {domain_name}. FreeStorageSpace alarm "
                f"will be skipped."
            )
            return [
                t
                for t in templates
                if t.get("configuration", {}).get("MetricName") != "FreeStorageSpace"
            ]

        enriched_templates: List[Dict[str, Any]] = []
        for template in templates:
            enriched_template = copy.deepcopy(template)
            config = enriched_template.get("configuration", {})

            if config.get("MetricName") == "FreeStorageSpace":
                config["Threshold"] = free_storage_threshold
                self.logger.debug(
                    f"Set FreeStorageSpace threshold to "
                    f"{free_storage_threshold} MiB for domain "
                    f"{domain_name}"
                )

            enriched_templates.append(enriched_template)

        return enriched_templates

    def extract_domain_name(self, arn: str) -> Optional[str]:
        """Extract OpenSearch domain name from ARN.

        OpenSearch ARN format:
            arn:aws:es:region:account:domain/domain-name

        Args:
            arn: OpenSearch domain ARN

        Returns:
            Domain name or None if extraction fails
        """
        try:
            parsed_arn = arnparse(arn)
            resource = parsed_arn.resource or ""

            if "/" in resource:
                parts = resource.split("/")
                if len(parts) >= 2:
                    return parts[1]

            return resource if resource else None

        except Exception as e:
            self.logger.error(
                f"Failed to extract domain name from ARN " f"{arn}: {str(e)}"
            )
            return None
