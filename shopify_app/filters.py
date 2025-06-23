# products/filters.py

import django_filters
from .models import Product

class ProductFilter(django_filters.FilterSet):
    """
    FilterSet for the Product model.
    Provides filtering capabilities for API endpoints.
    """
    price__gte = django_filters.NumberFilter(field_name='price', lookup_expr='gte', help_text="Filter by price greater than or equal to")
    price__lte = django_filters.NumberFilter(field_name='price', lookup_expr='lte', help_text="Filter by price less than or equal to")
    inventory_quantity__gte = django_filters.NumberFilter(field_name='inventory_quantity', lookup_expr='gte', help_text="Filter by quantity greater than or equal to")
    inventory_quantity__lte = django_filters.NumberFilter(field_name='inventory_quantity', lookup_expr='lte', help_text="Filter by quantity less than or equal to")

    class Meta:
        model = Product
        fields = {
            'name': ['icontains'], # Case-insensitive contains for product name
            'sku': ['exact', 'icontains'], # Exact match and case-insensitive contains for SKU
            'price': ['exact', 'gte', 'lte'], # Exact, greater than/equal, less than/equal for price
            'inventory_quantity': ['exact', 'gte', 'lte'], # Exact, greater than/equal, less than/equal for quantity
            'last_updated': ['gte', 'lte'], # Filter by date range for last updated
        }
