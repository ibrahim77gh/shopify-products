# products/views.py

from rest_framework import viewsets, filters, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.db import transaction, IntegrityError
import json
from django_filters.rest_framework import DjangoFilterBackend
import hmac
import hashlib

from .models import Product
from .serializers import ProductSerializer
from .filters import ProductFilter
import logging
from django.conf import settings
import base64


logger = logging.getLogger(__name__)

class ProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows products to be viewed or edited.
    Provides CRUD operations for Product model.
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    filterset_class = ProductFilter # Use our custom ProductFilter for advanced filtering
    search_fields = ['name', 'sku'] # Fields to search across

    def get_permissions(self):
        if self.action == 'list':
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]


class ShopifyWebhookView(APIView):
    """
    Handles Shopify webhooks for various events (e.g., product creation, inventory updates).
    This view implements Shopify's HMAC-SHA256 signature verification
    to ensure the request genuinely originates from Shopify.
    """
    permission_classes = [] # No authentication/permissions needed by default for webhooks;
                            # verification is handled internally by checking the signature.

    def post(self, request, *args, **kwargs):
        """
        Processes incoming Shopify webhook payloads.
        It verifies the HMAC signature and dispatches the payload
        to the appropriate handler based on the 'X-Shopify-Topic' header.
        """
        # 1. Shopify HMAC-SHA256 signature verification.
        hmac_header = request.headers.get('X-Shopify-Hmac-Sha256')
        webhook_secret = settings.SHOPIFY_WEBHOOK_SECRET.encode('utf-8')
        request_body = request.body # Raw body is needed for HMAC calculation

        # Calculate HMAC
        # hmac.new returns a hash object. We need its digest in bytes, then base64 encode it.
        calculated_hmac_digest = hmac.new(
            webhook_secret,
            request_body,
            hashlib.sha256
        ).digest() # Get the digest as bytes

        calculated_hmac_base64 = base64.b64encode(calculated_hmac_digest).decode('utf-8') # Base64 encode and decode to string

        if not hmac.compare_digest(calculated_hmac_base64, hmac_header):
            logger.warning(f"Webhook signature mismatch: Calculated '{calculated_hmac_base64}', Received '{hmac_header}'")
            return Response(
                {"error": "Unauthorized webhook request: Invalid HMAC signature."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 2. Parse payload and identify topic
        try:
            payload = json.loads(request_body)
            shopify_topic = request.headers.get('X-Shopify-Topic')
            logger.info(f"Received Shopify webhook for topic: {shopify_topic}")

            if shopify_topic == 'products/create':
                return self._handle_product_create(payload)
            elif shopify_topic == 'products/update':
                # Shopify 'products/update' webhook sends a full product object,
                # which can be used to update inventory for its variants.
                return self._handle_product_update(payload)
            else:
                logger.info(f"Unhandled Shopify webhook topic: {shopify_topic}")
                return Response(
                    {"message": f"Webhook received, but topic '{shopify_topic}' is not handled."},
                    status=status.HTTP_200_OK # Acknowledge receipt even if not handled
                )

        except json.JSONDecodeError:
            logger.error("Invalid JSON payload received for webhook.")
            return Response(
                {"error": "Invalid JSON payload."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception("An unexpected error occurred processing webhook.")
            return Response(
                {"error": f"An unexpected error occurred processing webhook: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _handle_product_create(self, payload):
        """
        Handles 'products/create' webhook.
        Creates new Product entries for each variant found in the payload.
        """
        try:
            product_title = payload.get('title', 'Unknown Product')
            variants = payload.get('variants', [])
            responses = []

            if not variants:
                logger.info(f"Product '{product_title}' created but has no variants to process.")
                return Response(
                    {"message": f"Product '{product_title}' created, no variants to process."},
                    status=status.HTTP_200_OK
                )

            with transaction.atomic():
                for variant in variants:
                    sku = variant.get('sku')
                    price = variant.get('price')
                    inventory_quantity = variant.get('inventory_quantity') # Note: this might be null if not tracked

                    if not sku:
                        logger.warning(f"Skipping variant for product '{product_title}' due to missing SKU: {variant}")
                        responses.append({"sku": "N/A", "status": "skipped", "reason": "Missing SKU"})
                        continue

                    if price is None:
                        price = 0.00 # Default price if not provided, or handle as error
                        logger.warning(f"Price not provided for SKU {sku}. Defaulting to 0.00.")

                    if inventory_quantity is None:
                        inventory_quantity = 0 # Default quantity if not provided, or handle as error
                        logger.info(f"Inventory quantity not provided for SKU {sku}. Defaulting to 0.")


                    try:
                        product, created = Product.objects.get_or_create(
                            sku=sku,
                            defaults={
                                'name': f"{product_title} - {variant.get('title', 'Default')}",
                                'price': price,
                                'inventory_quantity': inventory_quantity,
                            }
                        )
                        if created:
                            responses.append({"sku": sku, "status": "created", "product_id": product.id})
                            logger.info(f"Created new product entry for SKU: {sku}")
                        else:
                            # If product already exists (e.g., duplicate webhook, or SKU existed prior)
                            # We can choose to update it, or just log. For creation, we'll just log.
                            # The update webhook is more appropriate for actual updates.
                            responses.append({"sku": sku, "status": "exists", "product_id": product.id})
                            logger.info(f"Product with SKU '{sku}' already exists. Not re-creating.")
                    except IntegrityError:
                        # Catch race conditions if two webhooks try to create the same SKU simultaneously
                        logger.warning(f"Race condition: Product with SKU '{sku}' already exists during creation attempt.")
                        responses.append({"sku": sku, "status": "exists_race_condition"})
                    except Exception as e:
                        logger.error(f"Error creating product for SKU {sku}: {str(e)}")
                        responses.append({"sku": sku, "status": "error", "message": str(e)})

            # Respond with a summary of actions for all variants
            return Response(
                {"message": "Product creation webhook processed.", "details": responses},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.exception("Error in _handle_product_create method.")
            return Response(
                {"error": f"An error occurred during product creation processing: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    def _handle_product_update(self, payload):
        """
        Handles 'products/update' webhook.
        Updates inventory quantities for each variant found in the payload.
        This also covers updates to product name and price, if Shopify sends them.
        """
        try:
            product_title = payload.get('title', 'Unknown Product')
            variants = payload.get('variants', [])
            responses = []

            if not variants:
                logger.info(f"Product '{product_title}' updated but has no variants to process for inventory update.")
                return Response(
                    {"message": f"Product '{product_title}' updated, no variants to process."},
                    status=status.HTTP_200_OK
                )

            with transaction.atomic():
                for variant in variants:
                    sku = variant.get('sku')
                    price = variant.get('price')
                    inventory_quantity = variant.get('inventory_quantity')

                    if not sku:
                        logger.warning(f"Skipping variant for product '{product_title}' update due to missing SKU: {variant}")
                        responses.append({"sku": "N/A", "status": "skipped", "reason": "Missing SKU"})
                        continue

                    try:
                        # Attempt to get the product, and if it doesn't exist, log it.
                        # For 'update', we primarily focus on existing products.
                        product = Product.objects.select_for_update().get(sku=sku)

                        # Check if inventory_quantity has changed to avoid unnecessary updates
                        current_quantity = product.inventory_quantity
                        if inventory_quantity is not None and current_quantity != inventory_quantity:
                            # Calculate the change and use the atomic update method
                            change_amount = inventory_quantity - current_quantity
                            operation = 'add' if change_amount >= 0 else 'subtract'
                            success = product.update_inventory(abs(change_amount), operation)
                            if success:
                                responses.append({"sku": sku, "status": "inventory_updated", "old_qty": current_quantity, "new_qty": product.inventory_quantity})
                                logger.info(f"Inventory for SKU {sku} updated to {product.inventory_quantity}.")
                            else:
                                responses.append({"sku": sku, "status": "inventory_update_failed", "message": "Failed to apply inventory change."})
                                logger.warning(f"Failed to update inventory for SKU {sku} via webhook.")
                        else:
                            responses.append({"sku": sku, "status": "no_inventory_change"})
                            logger.info(f"No inventory change detected or quantity not provided for SKU {sku}.")

                        # Additionally, update other fields like name and price if they change
                        # This makes the "product update" webhook more comprehensive.
                        updated_fields = {}
                        if product.name != f"{product_title} - {variant.get('title', 'Default')}":
                            updated_fields['name'] = f"{product_title} - {variant.get('title', 'Default')}"
                        if price is not None and product.price != price:
                            updated_fields['price'] = price

                        if updated_fields:
                            Product.objects.filter(sku=sku).update(**updated_fields)
                            responses.append({"sku": sku, "status": "details_updated", "fields": updated_fields})
                            logger.info(f"Details for SKU {sku} updated: {updated_fields}")

                    except Product.DoesNotExist:
                        responses.append({"sku": sku, "status": "not_found", "message": "Product not found in local DB."})
                        logger.warning(f"Product with SKU '{sku}' not found during update webhook processing. Consider creating it if missing.")
                    except Exception as e:
                        logger.error(f"Error updating product for SKU {sku}: {str(e)}")
                        responses.append({"sku": sku, "status": "error", "message": str(e)})

            return Response(
                {"message": "Product update webhook processed.", "details": responses},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.exception("Error in _handle_product_update method.")
            return Response(
                {"error": f"An error occurred during product update processing: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
