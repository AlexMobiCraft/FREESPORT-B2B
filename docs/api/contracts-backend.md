# Backend API Contracts

**(Updated Scan: 2026-01-18)**

## Base URL
`/api/v1/`

## Products (`/products`)
- `GET /products/`: List products (supports filtering).
- `GET /products/{slug}/`: Retrieve product details.
- `GET /categories/`: List categories.
- `GET /categories-tree/`: Hierarchical category tree.
- `GET /brands/`: List brands.
- `GET /catalog/filters/`: Dynamic attribute filters.

## Cart (`/cart`)
- `GET /cart/`: Get current session cart.
- `DELETE /cart/clear/`: Empty the cart.
- `POST /cart/items/`: Add item to cart.
- `PATCH /cart/items/{id}/`: Update quantity.
- `DELETE /cart/items/{id}/`: Remove item.

## Orders (`/orders`)
- `POST /orders/`: Create order.
- `GET /orders/`: List user orders.

## Users (`/users`)
- `POST /users/register/`: Registration.
- `POST /users/token/`: Login (JWT).
- `GET /users/me/`: Current profile.
- `GET /users/company/`: B2B Company profile.

## Documentation
- Swagger UI: `/api/schema/swagger-ui/`
- ReDoc: `/api/schema/redoc/`