# Backend Architecture

## Executive Summary
Django-based REST API server following the 12-factor app methodology. It serves as the core business logic layer, handling data persistence, business rules, and external integrations (1C, Payments, Delivery).

## Technology Stack
- **Framework**: Django 5.2.7 + DRF 3.14
- **Database**: PostgreSQL 15
- **Async Task Queue**: Celery 5.4 + Redis 7.0
- **Documentation**: OpenAPI 3.0 (drf-spectacular)

## Core Domain Models
See [Data Models](./data-models-backend.md) for detailed schema.

- **Users**: Extended AbstractUser with Role-Based Access Control (RBAC).
- **Products**: EAV-like structure for variants and properties.
- **Orders**: Snapshot-based order processing.

## Architectural Patterns
- **Monolith Modular**: Code organized by business domains (apps).
- **Service Layer**: Business logic encapsulated in `services.py` (not views).
- **Signals**: Used for decoupled events (e.g., profile creation on user signup).
- **Asynchronous Processing**: Heavy tasks (imports, emails) offloaded to Celery.

## Detailed Documentation
- [Architecture Detail](./architecture/index.md)
- [API Views](./api-views-documentation.md)
