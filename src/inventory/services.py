"""
StockHub Inventory Service

Core business logic for stock management operations.
"""

import logging
from typing import Optional

from .models import Channel, MovementType, Product, StockMovement, StockReservation
from src.sync.services import MarketplaceSyncService

logger = logging.getLogger(__name__)


class StockService:
    """
    Handles all stock-related operations including movements,
    reservations, and inventory queries.
    """

    def __init__(self):
        self.sync_service = MarketplaceSyncService()

    def get_available_stock(self, product: Product) -> int:
        """
        Calculate the available stock for a product.

        Available = Physical - Reserved
        """
        reserved = StockReservation.objects.filter(
            product=product
        ).aggregate(total=models.Sum("quantity"))["total"] or 0

        return product.physical_stock - reserved

    def record_sale(
        self,
        product: Product,
        quantity: int,
        channel: Channel,
        reason: str = ""
    ) -> StockMovement:
        """
        Record a sale and update stock levels.

        Args:
            product: The product being sold
            quantity: Number of units sold (positive integer)
            channel: The sales channel where the sale occurred
            reason: Optional reason/reference for the sale

        Returns:
            The created StockMovement record
        """
        if quantity <= 0:
            raise ValueError("Sale quantity must be positive")

        if product.physical_stock < quantity:
            raise ValueError(
                f"Insufficient stock: {product.physical_stock} available, "
                f"{quantity} requested"
            )

        movement = StockMovement.objects.create(
            product=product,
            movement_type=MovementType.SALE,
            quantity=-quantity,
            channel=channel,
            reason=reason
        )

        product.physical_stock -= quantity
        product.save()

        logger.info(
            f"Recorded sale: {quantity}x {product.sku} on {channel.name}"
        )

        if product.is_below_threshold():
            self._send_stock_alert(product)

        self.sync_service.sync_product_stock(product)

        return movement

    def record_return(
        self,
        product: Product,
        quantity: int,
        channel: Optional[Channel] = None,
        reason: str = ""
    ) -> StockMovement:
        """
        Record a product return and update stock levels.

        Args:
            product: The product being returned
            quantity: Number of units returned (positive integer)
            channel: The channel the return came from (optional)
            reason: Reason for the return

        Returns:
            The created StockMovement record
        """
        if quantity <= 0:
            raise ValueError("Return quantity must be positive")

        movement = StockMovement.objects.create(
            product=product,
            movement_type=MovementType.RETURN,
            quantity=quantity,
            channel=channel,
            reason=reason
        )

        product.physical_stock += quantity
        product.save()

        logger.info(f"Recorded return: {quantity}x {product.sku}")

        self.sync_service.sync_product_stock(product)

        return movement

    def record_adjustment(
        self,
        product: Product,
        quantity: int,
        reason: str = ""
    ) -> StockMovement:
        """
        Record a manual stock adjustment.

        Used for inventory corrections, damage write-offs, etc.

        Args:
            product: The product being adjusted
            quantity: Adjustment amount (positive or negative)
            reason: Reason for the adjustment

        Returns:
            The created StockMovement record
        """
        new_stock = product.physical_stock + quantity
        if new_stock < 0:
            raise ValueError(
                f"Adjustment would result in negative stock: {new_stock}"
            )

        movement = StockMovement.objects.create(
            product=product,
            movement_type=MovementType.ADJUSTMENT,
            quantity=quantity,
            reason=reason
        )

        product.physical_stock = new_stock
        product.save()

        logger.info(
            f"Recorded adjustment: {quantity:+d} for {product.sku}. "
            f"New stock: {new_stock}"
        )

        self.sync_service.sync_product_stock(product)

        return movement

    def record_restock(
        self,
        product: Product,
        quantity: int,
        reason: str = ""
    ) -> StockMovement:
        """
        Record incoming stock from a supplier.

        Args:
            product: The product being restocked
            quantity: Number of units received (positive integer)
            reason: Reference/PO number for the restock

        Returns:
            The created StockMovement record
        """
        if quantity <= 0:
            raise ValueError("Restock quantity must be positive")

        movement = StockMovement.objects.create(
            product=product,
            movement_type=MovementType.RESTOCK,
            quantity=quantity,
            reason=reason
        )

        product.physical_stock += quantity
        product.save()

        logger.info(
            f"Recorded restock: {quantity}x {product.sku}. "
            f"New stock: {product.physical_stock}"
        )

        self.sync_service.sync_product_stock(product)

        return movement

    def create_reservation(
        self,
        product: Product,
        channel: Channel,
        quantity: int
    ) -> StockReservation:
        """
        Create a stock reservation for a channel.

        Args:
            product: The product to reserve
            channel: The channel to reserve for
            quantity: Number of units to reserve

        Returns:
            The created StockReservation record
        """
        available = self.get_available_stock(product)
        if quantity > available:
            raise ValueError(
                f"Cannot reserve {quantity} units. "
                f"Only {available} available."
            )

        reservation = StockReservation.objects.create(
            product=product,
            channel=channel,
            quantity=quantity
        )

        logger.info(
            f"Created reservation: {quantity}x {product.sku} "
            f"for {channel.name}"
        )

        return reservation

    def get_stock_movements(
        self,
        product: Product,
        movement_type: Optional[str] = None,
        limit: int = 100
    ) -> list[StockMovement]:
        """
        Retrieve stock movements for a product.

        Args:
            product: The product to query
            movement_type: Optional filter by movement type
            limit: Maximum number of records to return

        Returns:
            List of StockMovement records
        """
        queryset = StockMovement.objects.filter(product=product)

        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)

        return list(queryset[:limit])

    def get_low_stock_products(self) -> list[Product]:
        """
        Get all products that are at or below their alert threshold.

        Returns:
            List of Product records with low stock
        """
        products = Product.objects.all()
        return [p for p in products if p.is_below_threshold()]

    def _send_stock_alert(self, product: Product) -> None:
        """
        Send an alert that stock has fallen below threshold.

        Args:
            product: The product with low stock
        """
        logger.warning(
            f"LOW STOCK ALERT: {product.sku} ({product.name}) "
            f"is at {product.physical_stock} units "
            f"(threshold: {product.alert_threshold})"
        )
