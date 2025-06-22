# Django Inventory Backend

This project implements a simplified backend system using Python, Django, and Django REST Framework for managing product data, handling webhooks, and performing scheduled tasks.

## Features

* **REST API Endpoints:** CRUD operations for `Product` (Name, SKU, Price, Inventory Quantity, Last Updated Timestamp).
    * Filtering and searching capabilities (price, SKU, product name, quantity).
    * Basic token authentication restricting access to a specific user group (`API Users`).
* **Webhook Endpoint:** A dedicated endpoint (`/api/shopify-webhook/`) to handle product creation and inventory updates from Shopify, including HMAC signature verification.
* **Admin Interface Customization:**
    * Advanced filtering in Django admin.
    * Quick actions for bulk price updates (set to value, increase by percentage).
* **Nightly Background Tasks (Celery):**
    * Import mock product data from a CSV file.
    * Validate imported data and update inventory.
    * Generate and email a summary report of inventory changes.
    * Uses `django-celery-beat` for database-managed scheduling.

## Getting Started

### Prerequisites

* Docker and Docker Compose installed on your machine.
* (Optional, for manual testing outside Docker) Python 3.10+, pip, Redis server.

### Setup (Docker Compose)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/ibrahim77gh/shopify-products.git
    cd product_management
    ```

2.  **Create a `.env` file** in the project root (same directory as `docker-compose.yml`). This file will store your environment variables and should **NOT** be committed to version control (add it to your `.gitignore`).

    Example `.env` content:
    ```
    DJANGO_DATABASE_NAME=db.sqlite3
    DJANGO_DATABASE_ENGINE=django.db.backends.sqlite3
    DJANGO_ALLOWED_HOSTS=*
    SHOPIFY_WEBHOOK_SECRET=YOUR_SHOPIFY_WEBHOOK_SECRET_HERE
    ```
    **Remember to replace `YOUR_SHOPIFY_WEBHOOK_SECRET_HERE` with the actual secret from your Shopify webhook setup.**

3.  **Create a `mock_products.csv` file** in the project root (same directory as `docker-compose.yml`) with the following content:
    ```csv
    name,sku,price,inventory_quantity
    Red T-Shirt,TSHIRT-RED-S,19.99,150
    Blue Jeans,JEANS-BLUE-32,49.50,80
    Green Hoodie,HOODIE-GRN-L,35.00,50
    Laptop Pro,LAP-001,1200.00,10
    Wireless Mouse,MOU-002,25.00,200
    Red T-Shirt,TSHIRT-RED-S,20.00,160
    Invalid Product,,20.00,100
    Another Item,ITEM-004,abc,50
    ```

4.  **Build and run the Docker containers:**
    ```bash
    docker-compose up --build -d
    ```
    This command will:
    * Build the Django application image.
    * Start the `redis` service.
    * Start the `web` (Django) service.
    * Start the `celery_worker` service.
    * Start the `celery_beat` service, which will also run initial database migrations automatically.

5.  **Create a Django Superuser:**
    After the services are up, create a superuser for accessing the Django admin.
    ```bash
    docker-compose exec web python manage.py createsuperuser
    ```
    Follow the prompts to create your superuser account.

6.  **Create the 'API Users' Group:**
    This group is required for API access.
    ```bash
    docker-compose exec web python manage.py shell
    ```
    Inside the Django shell, run:
    ```python
    from django.contrib.auth.models import Group, User
    group, created = Group.objects.get_or_create(name='API Users')
    user = User.objects.get(username='YOUR_SUPERUSER_USERNAME') # Replace YOUR_SUPERUSER_USERNAME
    user.groups.add(group)
    exit()
    ```

7.  **Set up Celery Beat Schedules (via Django Admin):**
    * Open your browser and navigate to the Django admin: `http://localhost:8000/admin/`
    * Log in with your superuser credentials.
    * Under "DJANGO CELERY BEAT", go to "Periodic Tasks" and click "Add Periodic Task".
    * **Name:** `Nightly Product Import`
    * **Task:** `products.tasks.import_product_data_from_csv`
    * **Crontab:** Click "ADD CRONTAB SCHEDULE". Set `Minute: 0`, `Hour: 0` (for midnight), and `Day of week`, `Day of month`, `Month of year` to `*`. Save the Crontab schedule and then select it.
    * **Arguments (JSON list):** `[null, "your_admin_email@example.com"]` (replace with your desired recipient email). The `null` argument tells the task to read from `mock_products.csv`.
    * **Enabled:** Check this box.
    * Save the Periodic Task.

## API Usage

The API is available at `http://localhost:8000/api/`.

### Authentication

API endpoints (except `/api/shopify-webhook/`) require Token Authentication.

1.  **Get a Token:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"username":"YOUR_USERNAME", "password":"YOUR_PASSWORD"}' http://localhost:8000/api-token-auth/
    ```
    (Replace `YOUR_USERNAME` and `YOUR_PASSWORD` with an API user's credentials).
    You will receive a `{"token": "..."}` response.

2.  **Use the Token:**
    Include the token in the `Authorization` header for all authenticated requests:
    `Authorization: Token YOUR_AUTH_TOKEN`

### Product Endpoints

* **List Products:** `GET http://localhost:8000/api/products/`
    * Supports filtering (e.g., `?sku__icontains=TSHIRT`, `?price__gte=20.00`) and searching (`?search=Red`).
* **Create Product:** `POST http://localhost:8000/api/products/`
* **Retrieve Product:** `GET http://localhost:8000/api/products/<id>/`
* **Update Product:** `PUT/PATCH http://localhost:8000/api/products/<id>/`
* **Delete Product:** `DELETE http://localhost:8000/api/products/<id>/`

### Shopify Webhook

* **URL:** `http://localhost:8000/api/shopify-webhook/`
* **Method:** `POST`
* **Authentication:** This endpoint verifies requests using Shopify's HMAC-SHA256 signature.
    * **Important:** The `SHOPIFY_WEBHOOK_SECRET` is now read from the `.env` file. Ensure it's correctly set there.
    * **For local testing with Shopify:** You'll need a tunneling service like [ngrok](https://ngrok.com/) to expose your `http://localhost:8000` to the internet.

## Stopping the Services

To stop all Docker containers:
```bash
docker-compose down

To stop and remove all data (including Redis data and SQLite database):

docker-compose down -v

