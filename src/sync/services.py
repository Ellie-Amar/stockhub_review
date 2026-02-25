"""
StockHub Marketplace Sync Service

Handles synchronization of stock levels to external marketplaces.
"""

import logging
from typing import Any

import requests
from django.conf import settings

from src.inventory.models import Channel, Product

logger = logging.getLogger(__name__)


class MarketplaceSyncService:
    """
    Synchronizes stock levels with external marketplace APIs.

    Supports multiple channels including Amazon, Cdiscount, and custom APIs.
    """

    def __init__(self):
        self.channel_configs = {
            "Amazon": {
                "api_key": settings.AMAZON_API_KEY,
                "api_secret": settings.AMAZON_API_SECRET,
                "api_url": settings.AMAZON_API_URL,
            },
            "Cdiscount": {
                "api_key": settings.CDISCOUNT_API_KEY,
                "api_secret": settings.CDISCOUNT_API_SECRET,
                "api_url": settings.CDISCOUNT_API_URL,
            },
        }

    def sync_product_stock(self, product: Product) -> dict[str, bool]:
        """
        Sync a single product's stock to all active channels.

        Args:
            product: The product to sync

        Returns:
            Dict mapping channel name to sync success status
        """
        results = {}
        channels = Channel.objects.filter(is_active=True)

        for channel in channels:
            try:
                success = self._sync_to_channel(product, channel)
                results[channel.name] = success
            except Exception as e:
                logger.error(
                    f"Failed to sync {product.sku} to {channel.name}: {e}"
                )
                results[channel.name] = False

        return results

    def sync_all_products(self) -> dict[str, dict[str, bool]]:
        """
        Sync all products to all active channels.

        Returns:
            Nested dict: {product_sku: {channel_name: success}}
        """
        results = {}
        products = Product.objects.all()

        for product in products:
            results[product.sku] = self.sync_product_stock(product)

        return results

    def _sync_to_channel(self, product: Product, channel: Channel) -> bool:
        """
        Sync a product's stock to a specific channel.

        Args:
            product: The product to sync
            channel: The target channel

        Returns:
            True if sync was successful, False otherwise
        """
        config = self._get_channel_config(channel)

        payload = self._build_stock_payload(product, channel)

        try:
            response = requests.put(
                f"{config['api_url']}/inventory/{product.sku}",
                json=payload,
                headers=self._build_headers(config)
            )

            if response.status_code == 200:
                logger.info(
                    f"Successfully synced {product.sku} to {channel.name}: "
                    f"stock={product.physical_stock}"
                )
                return True
            else:
                logger.warning(
                    f"Sync failed for {product.sku} to {channel.name}: "
                    f"HTTP {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Sync error for {product.sku} to {channel.name}: {e}")
            return False

    def _get_channel_config(self, channel: Channel) -> dict[str, Any]:
        """
        Get API configuration for a channel.

        Tries predefined configs first, falls back to channel model data.
        """
        if channel.name in self.channel_configs:
            return self.channel_configs[channel.name]

        return {
            "api_key": channel.api_key,
            "api_secret": "",
            "api_url": channel.api_url,
        }

    def _build_stock_payload(
        self,
        product: Product,
        channel: Channel
    ) -> dict[str, Any]:
        """
        Build the API payload for a stock update.

        Args:
            product: The product being synced
            channel: The target channel

        Returns:
            Dict payload for the API request
        """
        return {
            "sku": product.sku,
            "quantity": product.physical_stock,
            "channel_id": str(channel.id),
        }

    def _build_headers(self, config: dict[str, Any]) -> dict[str, str]:
        """
        Build HTTP headers for marketplace API requests.

        Args:
            config: Channel configuration dict

        Returns:
            Dict of HTTP headers
        """
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
            "X-Api-Secret": config.get("api_secret", ""),
        }


class InventorySyncScheduler:
    """
    Schedules and manages periodic inventory syncs.

    Note: In production, this would be triggered by Celery beat.
    """

    def __init__(self):
        self.sync_service = MarketplaceSyncService()

    def run_full_sync(self) -> dict:
        """
        Execute a full inventory sync across all products and channels.

        Returns:
            Summary of sync results
        """
        logger.info("Starting full inventory sync")

        results = self.sync_service.sync_all_products()

        success_count = sum(
            1 for product_results in results.values()
            for success in product_results.values()
            if success
        )

        total_count = sum(
            len(product_results) for product_results in results.values()
        )

        logger.info(
            f"Full sync complete: {success_count}/{total_count} successful"
        )

        return {
            "total_syncs": total_count,
            "successful_syncs": success_count,
            "failed_syncs": total_count - success_count,
            "details": results,
        }
