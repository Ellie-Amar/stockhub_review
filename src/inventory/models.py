"""
StockHub Inventory Models

Data models for product inventory, stock movements, and channel management.
"""

import uuid
from django.db import models


class MovementType(models.TextChoices):
    """Types of stock movements."""
    SALE = "SALE", "Sale"
    RETURN = "RETURN", "Return"
    ADJUSTMENT = "ADJUSTMENT", "Manual Adjustment"
    RESTOCK = "RESTOCK", "Restock from Supplier"


class Product(models.Model):
    """
    Represents a product in the inventory system.

    Each product has a unique SKU and tracks its current stock level.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    physical_stock = models.IntegerField(default=0)
    alert_threshold = models.IntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"
        ordering = ["sku"]

    def __str__(self) -> str:
        return f"{self.sku} - {self.name}"

    def is_below_threshold(self) -> bool:
        """Check if stock is at or below the alert threshold."""
        return self.physical_stock <= self.alert_threshold


class Channel(models.Model):
    """
    Represents a sales channel (marketplace or website).

    Stores connection details for API integration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    api_key = models.CharField(max_length=255)
    api_url = models.URLField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "channels"

    def __str__(self) -> str:
        return self.name


class StockReservation(models.Model):
    """
    Represents stock reserved for a specific channel.

    Used to earmark inventory for promotions or channel-specific allocations.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reservations"
    )
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        related_name="reservations"
    )
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stock_reservations"

    def __str__(self) -> str:
        return f"{self.product.sku}: {self.quantity} reserved for {self.channel.name}"


class StockMovement(models.Model):
    """
    Records a change in stock level for audit purposes.

    Every increase or decrease in inventory should be logged as a movement.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="movements"
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices
    )
    quantity = models.IntegerField()
    channel = models.ForeignKey(
        Channel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movements"
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stock_movements"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.movement_type}: {self.quantity} x {self.product.sku}"
