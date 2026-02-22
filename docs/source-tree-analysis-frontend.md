# Frontend Source Tree Analysis

## Critical Directories

### `/frontend/src/app` (App Router)
- **`(blue)/`**: Default "Blue" theme routes.
  - `catalog/`: Catalog pages (grid, list, filters).
  - `product/[slug]/`: Product detail page.
  - `cart/`, `checkout/`: Order flow.
- **`(electric)/`**: Alternative "Electric Orange" theme routes (demo).
- **`(auth)/`**: Authentication routes (login, register).
- **`layout.tsx`**: Root layout.

### `/frontend/src/components`
- **`ui/`**: Reusable atomic components (Button, Checkbox, Input).
- **`business/`**: Business-logic components (ProductCard, SearchAutocomplete).
- **`layout/`**: Structural components (Header, Footer).

### `/frontend/src/services`
- **`productService.ts`**: API client for products.
- **`cartStore.ts`**: Zustand store for shopping cart.
- **`authStore.ts`**: Zustand store for user session.

### `/frontend/src/types`
- **`api.ts`**: TypeScript interfaces matching Backend API responses.

## Entry Points
- `src/app/layout.tsx`: Root React component.
- `src/middleware.ts`: Next.js middleware (auth protection, theme switching).
