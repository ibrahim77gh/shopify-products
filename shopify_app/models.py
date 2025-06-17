from django.db import models
from django.db.models import F # Used for atomic updates

class Product(models.Model):
    """
    Represents a product in the inventory system.
    """
    name = models.CharField(max_length=255, help_text="Name of the product")
    sku = models.CharField(max_length=100, unique=True, help_text="Stock Keeping Unit, must be unique")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price of the product")
    inventory_quantity = models.PositiveIntegerField(default=0, help_text="Current stock quantity")
    last_updated = models.DateTimeField(auto_now=True, help_text="Timestamp of the last update to this product")

    class Meta:
        # Define default ordering for queries
        ordering = ['name']
        # Add indexes for fields commonly used in queries (filtering, searching)
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['name']),
            models.Index(fields=['last_updated']),
            models.Index(fields=['price']),
            models.Index(fields=['inventory_quantity']),
        ]

    def __str__(self):
        """
        String representation of the Product object.
        """
        return f"{self.name} ({self.sku})"

    def update_inventory(self, quantity_change: int, operation: str = 'add'):
        """
        Updates the inventory quantity atomically.
        Args:
            quantity_change (int): The amount to change the quantity by.
            operation (str): 'add' to increase, 'subtract' to decrease.
        Returns:
            bool: True if update was successful, False otherwise.
        """
        if operation == 'add':
            # Use F() expression for atomic update to prevent race conditions
            self.inventory_quantity = F('inventory_quantity') + quantity_change
        elif operation == 'subtract':
            # Ensure quantity does not go below zero for subtraction
            if self.inventory_quantity - quantity_change < 0:
                print(f"Warning: Cannot reduce inventory below zero for SKU {self.sku}. Current: {self.inventory_quantity}, Attempted decrease: {quantity_change}")
                return False
            self.inventory_quantity = F('inventory_quantity') - quantity_change
        else:
            print(f"Error: Invalid operation '{operation}' for inventory update.")
            return False

        # Save the instance to apply the F() expression and update last_updated
        self.save(update_fields=['inventory_quantity', 'last_updated'])
        # Refresh from DB to get the actual updated value if needed immediately
        self.refresh_from_db()
        return True

