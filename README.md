# Django Inventory Backend

This project implements a simplified backend system using Python, Django, and Django REST Framework for managing product data, handling webhooks, and performing scheduled tasks.

## Features

* **JWT Authentication:** Secure user authentication using JSON Web Tokens with the `djoser` package.
    * Email verification for new accounts.
    * Password reset functionality.
    * Token refresh capabilities.
* **REST API Endpoints:** CRUD operations for `Product` (Name, SKU, Price, Inventory Quantity, Last Updated Timestamp).
    * Filtering and searching capabilities (price, SKU, product name, quantity).
    * Basic token authentication restricting access to only authenticated users.
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
* (Optional, for manual testing outside Docker) Python 3.12, pip, Redis server.

### Setup (Docker Compose)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/ibrahim77gh/shopify-products.git
    cd product_management
    ```

2.  **Create a `.env` file** in the project root (same directory as `docker-compose.yml`). This file will store your environment variables and should **NOT** be committed to version control (add it to your `.gitignore`).

    Example `.env` content:
    ```
    DEBUG=<True or False>
    DJANGO_ALLOWED_HOSTS=*
    
    # Database Configuration
    DB_NAME=<your_database_name>
    DB_USER=<your_database_username>
    DB_PASSWORD=<your_database_password>
    DB_HOST=<your_database_host>
    DB_PORT=<your_database_port>
    
    # For SQLite fallback (optional)
    DJANGO_DATABASE_NAME=db.sqlite3
    DJANGO_DATABASE_ENGINE=django.db.backends.sqlite3
    
    # Shopify Integration
    SHOPIFY_WEBHOOK_SECRET=<your_shopify_webhook_secret>
    
    # Email Configuration
    EMAIL_HOST_PASSWORD=<your_email_password>
    ```
    **Note: These are placeholder values. Use appropriate values for your environment.**


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

6.  **Set up Celery Beat Schedules (via Django Admin):**
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

API endpoints (except `/api/shopify-webhook/`) require JWT Authentication.

1. **Register a New User:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"email":"user@example.com", "password":"secure_password", "re_password":"secure_password"}' http://localhost:8000/auth/users/
    ```

2. **Get JWT Token:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"email":"email", "password":"secure_password"}' http://localhost:8000/auth/jwt/create/
    ```
    You will receive a response with `access` and `refresh` tokens.

3. **Use the Token:**
    Include the access token in the Authorization header for all authenticated requests:
    `Authorization: JWT YOUR_ACCESS_TOKEN`

4. **Refresh Token:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"refresh":"YOUR_REFRESH_TOKEN"}' http://localhost:8000/auth/jwt/refresh/
    ```

5. **Verify Token:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"token":"YOUR_ACCESS_TOKEN"}' http://localhost:8000/auth/jwt/verify/
    ```

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

