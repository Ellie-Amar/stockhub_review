"""
StockHub Webhook Handlers

HTTP endpoints for receiving notifications from marketplaces.
"""

import json
import logging
from typing import Any

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from src.inventory.models import Channel, MovementType, Product, StockMovement
from src.sync.services import MarketplaceSyncService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class SaleWebhookView(View):
    """
    Handles incoming sale notifications from marketplaces.

    Expected payload:
    {
        "event_type": "sale",
        "sku": "PROD-001",
        "quantity": 2,
        "channel": "Amazon",
        "order_id": "ORD-12345",
        "timestamp": "2024-01-15T10:30:00Z"
    }
    """

    def post(self, request) -> JsonResponse:
        """Process an incoming sale webhook."""
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"error": "Invalid JSON payload"},
                status=400
            )

        sku = payload.get("sku")
        quantity = payload.get("quantity", 1)
        channel_name = payload.get("channel")
        order_id = payload.get("order_id", "")

        if not sku:
            return JsonResponse(
                {"error": "Missing required field: sku"},
                status=400
            )

        try:
            product = Product.objects.get(sku=sku)
        except Product.DoesNotExist:
            return JsonResponse(
                {"error": f"Product not found: {sku}"},
                status=404
            )

        channel = None
        if channel_name:
            try:
                channel = Channel.objects.get(name=channel_name)
            except Channel.DoesNotExist:
                logger.warning(f"Unknown channel in webhook: {channel_name}")

        if product.physical_stock < quantity:
            logger.error(
                f"Oversell detected: {sku} has {product.physical_stock} units, "
                f"but sale requested {quantity}"
            )
            return JsonResponse(
                {"error": "Insufficient stock"},
                status=409
            )

        sync_service = MarketplaceSyncService()
        sync_service.sync_product_stock(product)

        movement = StockMovement.objects.create(
            product=product,
            movement_type=MovementType.SALE,
            quantity=-quantity,
            channel=channel,
            reason=f"Order: {order_id}" if order_id else ""
        )

        product.physical_stock -= quantity
        product.save()

        logger.info(
            f"Processed sale webhook: {quantity}x {sku} "
            f"(Order: {order_id}, Channel: {channel_name})"
        )

        return JsonResponse({
            "status": "success",
            "movement_id": str(movement.id),
            "new_stock": product.physical_stock
        })


@method_decorator(csrf_exempt, name="dispatch")
class ReturnWebhookView(View):
    """
    Handles incoming return notifications from marketplaces.

    Expected payload:
    {
        "event_type": "return",
        "sku": "PROD-001",
        "quantity": 1,
        "channel": "Amazon",
        "return_id": "RET-12345",
        "reason": "Customer changed mind"
    }
    """

    def post(self, request) -> JsonResponse:
        """Process an incoming return webhook."""
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"error": "Invalid JSON payload"},
                status=400
            )

        sku = payload.get("sku")
        quantity = payload.get("quantity", 1)
        channel_name = payload.get("channel")
        return_id = payload.get("return_id", "")
        reason = payload.get("reason", "")

        if not sku:
            return JsonResponse(
                {"error": "Missing required field: sku"},
                status=400
            )

        try:
            product = Product.objects.get(sku=sku)
        except Product.DoesNotExist:
            return JsonResponse(
                {"error": f"Product not found: {sku}"},
                status=404
            )

        channel = None
        if channel_name:
            try:
                channel = Channel.objects.get(name=channel_name)
            except Channel.DoesNotExist:
                logger.warning(f"Unknown channel in webhook: {channel_name}")

        movement = StockMovement.objects.create(
            product=product,
            movement_type=MovementType.RETURN,
            quantity=quantity,
            channel=channel,
            reason=f"Return {return_id}: {reason}" if return_id else reason
        )

        product.physical_stock += quantity
        product.save()

        sync_service = MarketplaceSyncService()
        sync_service.sync_product_stock(product)

        logger.info(
            f"Processed return webhook: {quantity}x {sku} "
            f"(Return: {return_id}, Channel: {channel_name})"
        )

        return JsonResponse({
            "status": "success",
            "movement_id": str(movement.id),
            "new_stock": product.physical_stock
        })


@method_decorator(csrf_exempt, name="dispatch")
class StockAdjustmentWebhookView(View):
    """
    Handles stock adjustment notifications from warehouse systems.

    Expected payload:
    {
        "event_type": "adjustment",
        "sku": "PROD-001",
        "quantity": -5,
        "reason": "Inventory count correction"
    }
    """

    def post(self, request) -> JsonResponse:
        """Process a stock adjustment webhook."""
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"error": "Invalid JSON payload"},
                status=400
            )

        sku = payload.get("sku")
        quantity = payload.get("quantity")
        reason = payload.get("reason", "")

        if not sku:
            return JsonResponse(
                {"error": "Missing required field: sku"},
                status=400
            )

        if quantity is None:
            return JsonResponse(
                {"error": "Missing required field: quantity"},
                status=400
            )

        try:
            product = Product.objects.get(sku=sku)
        except Product.DoesNotExist:
            return JsonResponse(
                {"error": f"Product not found: {sku}"},
                status=404
            )

        new_stock = product.physical_stock + quantity
        if new_stock < 0:
            return JsonResponse(
                {"error": f"Adjustment would result in negative stock: {new_stock}"},
                status=400
            )

        movement = StockMovement.objects.create(
            product=product,
            movement_type=MovementType.ADJUSTMENT,
            quantity=quantity,
            reason=reason
        )

        product.physical_stock = new_stock
        product.save()

        sync_service = MarketplaceSyncService()
        sync_service.sync_product_stock(product)

        logger.info(
            f"Processed adjustment webhook: {quantity:+d} for {sku}. "
            f"New stock: {new_stock}"
        )

        return JsonResponse({
            "status": "success",
            "movement_id": str(movement.id),
            "new_stock": product.physical_stock
        })
