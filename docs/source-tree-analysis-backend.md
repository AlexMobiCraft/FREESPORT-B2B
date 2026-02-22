# Backend Source Tree Analysis

## Critical Directories

### `/backend/apps` (Django Apps)
- **`products/`**: Catalog logic (Models: Product, Variant, Brand, Category).
- **`users/`**: Custom User model, B2B logic, Authentication.
- **`orders/`**: Order processing, payments, delivery.
- **`cart/`**: Shopping cart management (Redis-backed).
- **`common/`**: Shared utilities, abstract models.

### `/backend/freesport` (Project Config)
- **`settings/`**: Modular settings (base, dev, prod).
- **`urls.py`**: Root URL routing.
- **`celery.py`**: Async task configuration.

### `/backend/data`
- **`import_1c/`**: XML files storage for 1C integration testing.

## Entry Points
- `manage.py`: Django CLI entry point.
- `wsgi.py` / `asgi.py`: Web server entry points.
