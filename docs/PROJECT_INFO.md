# **Project Overview**

This is a full-stack e-commerce platform for selling sporting goods, designed as an API-first solution for both B2B and B2C sales. The project is a monorepo with a Django backend and a Next.js frontend.

## **Project Architecture**

- **API-First + SSR/SSG Approach:** Ensures SEO optimization and high performance. The decoupling of frontend and backend allows for independent development cycles.  
- **Next.js Hybrid Rendering:** Utilizes Static Site Generation (SSG) for static pages, Server-Side Rendering (SSR) for dynamic content, and Incremental Static Regeneration (ISR) for catalogs.  
- **BFF (Backend for Frontend) Layer:** Next.js API Routes act as an intermediary layer to aggregate data and enhance security between the client and the main API.  
- **Monorepo Structure:** Simplifies management of shared components, configurations, and dependencies across the entire platform.

**Technology Stack:**

**Backend:**

- **Framework:** Django 4.2 LTS with Django REST Framework 3.14+  
- **Database:** PostgreSQL 15+ (with table partitioning and JSONB support)  
- **Cache:** Redis 7.0+ (for caching and sessions)  
- **Authentication:** JWT tokens with a refresh strategy  
- **Async Tasks:** Celery with Celery Beat for background jobs and scheduling  
- **API Documentation:** drf-spectacular for OpenAPI 3.1.0 specification

**Frontend:**

- **Framework:** Next.js 15.5.7 with TypeScript 5.0+  
- **UI Library:** React 19.1.0  
- **State Management:** Zustand 4.5.7 (state management)  
- **Styling:** Tailwind CSS 4.0  
- **Form Management:** React Hook Form 7.62.0  
- **Testing:** Vitest 2.1.5 and React Testing Library  16.3.0
- **API Mocking:** MSW 2.12.2

**Infrastructure:**

- **Web Server/Proxy:** Nginx (for reverse proxy, SSL, load balancing)  
- **Containerization:** Docker and Docker Compose  
- **CI/CD:** GitHub Actions

## **Django App Structure**

The project uses a modular Django apps architecture:

- apps/banners/: Управление баннерами Hero-секции с таргетингом по группам пользователей (гости, авторизованные, тренеры, оптовики, федералы).
- apps/users/: Manages users and a role-based system (7 roles: retail, wholesale_level1-3, trainer, federation_rep, admin).  
- apps/products/: Handles the product catalog, brands, and categories with multi-level pricing.  
- apps/orders/: Contains the order system supporting both B2B/B2C processes.  
- apps/cart/: Manages the shopping cart for both authenticated and guest users.  
- apps/common/: Общие утилиты, аудит, а также управление контентом: новости, блог и подписки на рассылку.

## **Key Data Models**

- **User Model:** Features a role-based system with 7 distinct user roles, each with different pricing tiers. Includes B2B-specific fields like company_name and tax_id.  
- **Product Model:** Supports multi-level pricing corresponding to user roles. Includes informational prices for B2B (RRP, MSRP), uses a JSONB field for dynamic product specifications, integrates with an ERP via onec_id, and has computed properties like is_in_stock.  
- **Order Model:** Designed to handle both B2B and B2C workflows, capturing a snapshot of product data at the time of purchase. It integrates with payment systems and includes order statuses with an audit trail.

## **Building and Running**

### **Docker**

The recommended way to run the project is with Docker Compose.

**Local Development:**

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d
```

**Production:**

```bash
docker compose --env-file .env.prod -f docker/docker-compose.prod.yml up -d
```

**Stop and remove all services:**

```bash
# Local
docker compose --env-file .env -f docker/docker-compose.yml down

# Production  
docker compose --env-file .env.prod -f docker/docker-compose.prod.yml down
```

The following services will be started:

- db: PostgreSQL database  
- redis: Redis cache  
- backend: Django API  
- frontend: Next.js application  
- nginx: Nginx reverse proxy

### **Local Development**

**Backend**

1. Navigate to the backend directory.  
2. Create a virtual environment: python -m venv venv  
3. Activate it: source venv/bin/activate (on Windows, use venv\Scripts\activate)  
4. Install dependencies: pip install -r requirements.txt  
5. Run the development server: python manage.py runserver 8001  
6. Run Celery workers (in separate terminals):  
   celery -A freesport worker --loglevel=info  
   celery -A freesport beat --loglevel=info

**Frontend**

1. Navigate to the frontend directory.  
2. Install dependencies: npm install  
3. Run the development server: npm run dev

## **Project Structure (Frontend)**

The frontend uses **Next.js Route Groups** for multi-theme architecture. 
See `frontend/src/app/` for details.

### **Theme Switching**

Set `ACTIVE_THEME` in `.env` to control root URL (`/`) redirect:
- `coming_soon` → `/coming-soon` (placeholder page)
- `blue` → `/home` (Blue Theme - Main Page)
- `electric_orange` → `/electric` (Electric Orange Theme)

> [!IMPORTANT]
> In production, ensure `ACTIVE_THEME` is explicitly set in `.env.prod`. If not set, it defaults to `coming_soon`.

### **Performance & Troubleshooting**

- **SSR Throttle Limits:** To prevent `429 Too Many Requests` during Server-Side Rendering, the `anon` throttle rate in `production.py` is increased to `6000/min`.

### **Key Routes**

- `/catalog` — Product catalog (Blue Theme)
- `/product/[slug]` — Product detail page
- `/cart`, `/checkout` — Shopping cart and checkout
- `/news`, `/blog` — Content pages
- `/electric` — Electric Orange theme demo

### **Services**

- `services/newsService.ts` — News API
- `services/blogService.ts` — Blog API

## **Development Conventions**

### **Git Workflow**

- main: Production branch (protected)  
- develop: Main development branch (protected)  
- feature/*: Branches for new features  
- hotfix/*: Branches for critical bug fixes

### **Testing Strategy**

- **Testing Pyramid:** E2E Tests (Playwright) > Integration Tests (Pytest + APIClient) > Unit Tests (Pytest, Jest).
- **Technology Stack:**
  - **Backend:** `pytest`, `pytest-django`, `Factory Boy`, `pytest-mock`.
  - **Frontend:** `Vitest`/`Jest`, `React Testing Library`, `MSW`.

**Backend Test Commands**

- **CRITICAL**: Запуск ТОЛЬКО через Docker.
- **Command**: `docker compose --env-file .env -f docker/docker-compose.yml exec backend pytest [args]`

**Frontend Test Commands**

```bash
npm test                    # Run all tests
npm test --watch            # Run tests in watch mode
npm run test:coverage       # Generate a coverage report
```

### **Code Style**

**Backend**: Black, Flake8, isort, mypy.
**Frontend**: ESLint, Tailwind CSS.

## **Integrations**

- **ERP (1C):** 1C Sync architecture details: `docs/architecture/import-architecture.md`
- **Payment Gateways:** YuKassa for online payments.  
- **Shipping Services:** CDEK and Boxberry.
