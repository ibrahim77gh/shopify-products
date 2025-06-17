from rest_framework import serializers
from .models import Product

class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for the Product model.
    Converts Product model instances to JSON and vice versa.
    """
    class Meta:
        model = Product
        fields = '__all__' # Include all fields from the Product model
        read_only_fields = ('last_updated',) 