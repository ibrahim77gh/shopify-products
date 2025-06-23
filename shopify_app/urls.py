from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, ShopifyWebhookView

router = DefaultRouter()
router.register(r'products', ProductViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('shopify-webhook/', ShopifyWebhookView.as_view(), name='shopify_webhook'),
]
