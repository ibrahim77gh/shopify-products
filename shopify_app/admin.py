# products/admin.py

from django.contrib import admin
from django.db import transaction
from django.template.defaultfilters import pluralize
from django.contrib import messages # For displaying success/error messages in admin

from .models import Product

# Define a custom admin action for bulk price updates
@admin.action(description='Set selected products price to a specific value')
def set_price_to_value(modeladmin, request, queryset):
    """
    Admin action to set the price of selected products to a specific value.
    This action will prompt the user for a price.
    """
    if 'apply' in request.POST:
        # User has submitted the form with a price
        new_price_str = request.POST.get('new_price')
        if not new_price_str:
            modeladmin.message_user(request, "Please enter a price.", level=messages.ERROR)
            return

        try:
            new_price = float(new_price_str)
            if new_price < 0:
                modeladmin.message_user(request, "Price cannot be negative.", level=messages.ERROR)
                return
        except ValueError:
            modeladmin.message_user(request, "Invalid price entered. Please enter a number.", level=messages.ERROR)
            return

        updated_count = 0
        with transaction.atomic():
            for product in queryset:
                if product.price != new_price: # Only update if price actually changes
                    product.price = new_price
                    product.save(update_fields=['price', 'last_updated'])
                    updated_count += 1
        
        if updated_count > 0:
            modeladmin.message_user(request, f"Successfully set price to {new_price} for {updated_count} product{pluralize(updated_count)}.", level=messages.SUCCESS)
        else:
            modeladmin.message_user(request, "No products had their price changed (perhaps already at the target price).", level=messages.INFO)
        return

    # If 'apply' is not in request.POST, it's the initial form display
    # Render a custom form to ask for the new price
    # We can use Django's built-in change_list.html for rendering custom forms for actions
    # by providing context.
    return modeladmin.render_change_list(request, extra_context={
        'title': 'Set Price for Products',
        'action_name': 'set_price_to_value',
        'selected_ids': ','.join(str(pk) for pk in queryset.values_list('pk', flat=True)),
        'form_template': 'admin/products/product/set_price_action_form.html', # Path to custom form template
        'media': modeladmin.media, # Include admin media for styling
    })


# Define another admin action for bulk price increase by percentage
@admin.action(description='Increase selected products price by percentage')
def increase_price_by_percentage(modeladmin, request, queryset):
    """
    Admin action to increase the price of selected products by a percentage.
    This action will prompt the user for a percentage.
    """
    if 'apply' in request.POST:
        percentage_str = request.POST.get('percentage_increase')
        if not percentage_str:
            modeladmin.message_user(request, "Please enter a percentage.", level=messages.ERROR)
            return

        try:
            percentage = float(percentage_str)
            if not (0 <= percentage <= 1000): # Allow up to 1000% increase
                modeladmin.message_user(request, "Percentage must be between 0 and 1000.", level=messages.ERROR)
                return
        except ValueError:
            modeladmin.message_user(request, "Invalid percentage entered. Please enter a number.", level=messages.ERROR)
            return

        updated_count = 0
        with transaction.atomic():
            for product in queryset:
                original_price = product.price
                new_price = original_price * (1 + (percentage / 100))
                # Ensure price is rounded correctly to 2 decimal places
                new_price = round(new_price, 2)
                if new_price != original_price: # Only update if price actually changes
                    product.price = new_price
                    product.save(update_fields=['price', 'last_updated'])
                    updated_count += 1
        
        if updated_count > 0:
            modeladmin.message_user(request, f"Successfully increased price by {percentage}% for {updated_count} product{pluralize(updated_count)}.", level=messages.SUCCESS)
        else:
            modeladmin.message_user(request, "No products had their price changed.", level=messages.INFO)
        return

    return modeladmin.render_change_list(request, extra_context={
        'title': 'Increase Price by Percentage',
        'action_name': 'increase_price_by_percentage',
        'selected_ids': ','.join(str(pk) for pk in queryset.values_list('pk', flat=True)),
        'form_template': 'admin/products/product/increase_price_action_form.html', # Path to custom form template
        'media': modeladmin.media,
    })


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Customizes the Django admin interface for the Product model.
    """
    list_display = ('name', 'sku', 'price', 'inventory_quantity', 'last_updated')
    search_fields = ('name', 'sku') # Basic search at the top of the admin list
    
    # Advanced filtering options on the right sidebar
    list_filter = (
        'sku', # Direct filter for SKU
        'name', # Direct filter for product name
        ('last_updated', admin.DateFieldListFilter), # Date range filter for last_updated
        'price', # Numeric filter for price
        'inventory_quantity', # Numeric filter for inventory quantity
    )

    # Enable date hierarchy for last_updated for quick navigation by year/month/day
    date_hierarchy = 'last_updated'

    # Add quick actions for bulk updates
    actions = [set_price_to_value, increase_price_by_percentage]

    # Custom template for the bulk price update action form
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        # Add a custom URL for rendering action forms if needed more generically
        # For our case, render_change_list is used, which often handles it.
        return urls

    def changelist_view(self, request, extra_context=None):
        # Override changelist_view to pass extra context for action forms
        extra_context = extra_context or {}
        
        # This will be used by our custom admin action form templates
        # It's crucial for the form to know which products are selected.
        if 'action' in request.POST and request.POST['action'] in self.actions and 'select_across' in request.POST:
            selected_ids = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
            extra_context['selected_ids'] = ','.join(selected_ids)
            # Pass the action itself to the context if needed for specific rendering logic
            extra_context['action_name'] = request.POST['action']
            # Pass the current form template based on the action selected
            if request.POST['action'] == 'set_price_to_value':
                extra_context['form_template'] = 'admin/products/product/set_price_action_form.html'
            elif request.POST['action'] == 'increase_price_by_percentage':
                extra_context['form_template'] = 'admin/products/product/increase_price_action_form.html'

        return super().changelist_view(request, extra_context=extra_context)

