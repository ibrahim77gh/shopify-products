# products/tasks.py

import csv
import os
import io
import logging
from datetime import datetime

from celery import shared_task
from django.conf import settings
from django.db import transaction, IntegrityError
from django.core.mail import send_mail

from .models import Product

logger = logging.getLogger(__name__)

# Define a mock CSV file path for demonstration purposes.
# In a real application, you might get this path from an argument,
# a shared storage location, or dynamically generated.
MOCK_CSV_FILE_PATH = os.path.join(settings.BASE_DIR, 'mock_products.csv')

@shared_task(bind=True)
def import_product_data_from_csv(self, csv_data_string=None, report_email_recipient='admin@inventory.com'):
    """
    Task 1 & 2: Imports product data from a CSV string,
    validates it, and either creates new products or updates
    existing inventory quantities.

    Args:
        csv_data_string (str): A string containing CSV data. If None, it attempts
                               to read from MOCK_CSV_FILE_PATH.
        report_email_recipient (str): The email address to send the summary report to.
    """
    import_summary = {
        'total_rows': 0,
        'created_count': 0,
        'updated_count': 0,
        'skipped_count': 0,
        'errors': [],
        'products_with_inventory_change': [] # To track products for the report
    }

    logger.info(f"Starting product data import task (Task ID: {self.request.id})...")

    # Use io.StringIO to treat the string as a file for csv.reader
    if csv_data_string:
        csv_file_like_object = io.StringIO(csv_data_string)
        logger.info("Importing from provided CSV data string.")
    else:
        # If no CSV string provided, try to read from the mock file path
        if not os.path.exists(MOCK_CSV_FILE_PATH):
            error_msg = f"Mock CSV file not found at {MOCK_CSV_FILE_PATH}. Please create it."
            logger.error(error_msg)
            import_summary['errors'].append(error_msg)
            # Proceed to generate report with errors
            return generate_and_email_inventory_report.delay(import_summary, report_email_recipient)
        
        logger.info(f"Importing from mock CSV file at: {MOCK_CSV_FILE_PATH}")
        try:
            with open(MOCK_CSV_FILE_PATH, 'r', encoding='utf-8') as f:
                csv_file_like_object = f.read()
            csv_file_like_object = io.StringIO(csv_file_like_object)
        except Exception as e:
            error_msg = f"Error reading mock CSV file: {str(e)}"
            logger.error(error_msg)
            import_summary['errors'].append(error_msg)
            return generate_and_email_inventory_report.delay(import_summary, report_email_recipient)


    reader = csv.DictReader(csv_file_like_object)
    
    # Expected CSV columns
    expected_headers = ['name', 'sku', 'price', 'inventory_quantity']
    if not all(header in reader.fieldnames for header in expected_headers):
        error_msg = f"CSV headers do not match expected: {expected_headers}. Found: {reader.fieldnames}"
        logger.error(error_msg)
        import_summary['errors'].append(error_msg)
        return generate_and_email_inventory_report.delay(import_summary, report_email_recipient)

    for row_num, row in enumerate(reader, 1):
        import_summary['total_rows'] += 1
        sku = row.get('sku')
        name = row.get('name')
        price_str = row.get('price')
        inventory_qty_str = row.get('inventory_quantity')

        # Basic validation
        if not sku or not name or not price_str or not inventory_qty_str:
            import_summary['skipped_count'] += 1
            import_summary['errors'].append(f"Row {row_num}: Missing data (SKU, Name, Price, or Quantity) for SKU '{sku or 'N/A'}'. Row: {row}")
            logger.warning(f"Skipping row {row_num} due to missing data: {row}")
            continue

        try:
            price = float(price_str)
            inventory_quantity = int(inventory_qty_str)
            if price < 0 or inventory_quantity < 0:
                raise ValueError("Price or inventory quantity cannot be negative.")
        except ValueError as e:
            import_summary['skipped_count'] += 1
            import_summary['errors'].append(f"Row {row_num}: Invalid numeric data for SKU '{sku}': {e}. Row: {row}")
            logger.warning(f"Skipping row {row_num} due to invalid numeric data: {row}")
            continue

        try:
            with transaction.atomic():
                product, created = Product.objects.get_or_create(
                    sku=sku,
                    defaults={
                        'name': name,
                        'price': price,
                        'inventory_quantity': inventory_quantity,
                    }
                )
                if created:
                    import_summary['created_count'] += 1
                    import_summary['products_with_inventory_change'].append(f"Created: {name} (SKU: {sku}) with qty {inventory_quantity}")
                    logger.info(f"Created new product: {name} (SKU: {sku})")
                else:
                    # Product exists, update its details and inventory if changed
                    # Only update if there's an actual change to avoid unnecessary DB writes and last_updated triggers
                    initial_inventory = product.inventory_quantity
                    initial_price = product.price
                    initial_name = product.name

                    # Update fields only if they are different
                    needs_update = False
                    if product.name != name:
                        product.name = name
                        needs_update = True
                    if product.price != price:
                        product.price = price
                        needs_update = True
                    
                    # For inventory, we explicitly track changes for reporting
                    if product.inventory_quantity != inventory_quantity:
                        product.inventory_quantity = inventory_quantity
                        needs_update = True
                        import_summary['products_with_inventory_change'].append(f"Updated Inventory: {name} (SKU: {sku}) from {initial_inventory} to {inventory_quantity}")

                    if needs_update:
                        product.save(update_fields=['name', 'price', 'inventory_quantity', 'last_updated'])
                        import_summary['updated_count'] += 1
                        logger.info(f"Updated existing product: {name} (SKU: {sku})")
                    else:
                        logger.info(f"Product: {name} (SKU: {sku}) already up-to-date. No changes applied.")

        except IntegrityError:
            # This can happen in very rare race conditions if another process
            # tries to create the same SKU at the exact same moment.
            import_summary['errors'].append(f"Row {row_num}: Race condition creating SKU '{sku}'. It might already exist.")
            logger.warning(f"IntegrityError for SKU: {sku}. Likely a race condition.")
        except Exception as e:
            import_summary['skipped_count'] += 1
            import_summary['errors'].append(f"Row {row_num}: Unhandled error for SKU '{sku}': {str(e)}. Row: {row}")
            logger.error(f"Error processing row {row_num} for SKU '{sku}': {str(e)}")

    logger.info("Product data import task completed.")

    # Chain the reporting task
    return generate_and_email_inventory_report.delay(import_summary, report_email_recipient)


@shared_task
def generate_and_email_inventory_report(import_summary, recipient_email):
    """
    Task 3: Generates a summary report of inventory updates and emails it.

    Args:
        import_summary (dict): The summary dictionary from the import_product_data_from_csv task.
        recipient_email (str): The email address to send the report to.
    """
    logger.info(f"Generating and emailing inventory report to {recipient_email}...")

    report_lines = [
        f"Inventory Import and Update Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "--- Summary ---",
        f"Total rows processed from CSV: {import_summary['total_rows']}",
        f"New products created: {import_summary['created_count']}",
        f"Existing products updated: {import_summary['updated_count']}",
        f"Rows skipped due to errors/missing data: {import_summary['skipped_count']}\n"
    ]

    if import_summary['products_with_inventory_change']:
        report_lines.append("--- Products with Inventory Changes ---")
        report_lines.extend(import_summary['products_with_inventory_change'])
        report_lines.append("\n")

    if import_summary['errors']:
        report_lines.append("--- Errors/Warnings ---")
        report_lines.extend(import_summary['errors'])
        report_lines.append("\n")
    else:
        report_lines.append("No major errors reported during import.\n")

    report_content = "\n".join(report_lines)

    try:
        send_mail(
            subject='Daily Inventory Import and Update Report',
            message=report_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False, # Set to True in production if email failures shouldn't halt the process
        )
        logger.info(f"Inventory report successfully emailed to {recipient_email}.")
    except Exception as e:
        logger.error(f"Failed to send inventory report email to {recipient_email}: {str(e)}")

