# Backend Data Models

**(Updated Scan: 2026-01-18)**

## Users (`apps.users.models`)

### `User` (AbstractUser)

Custom user model using email as username.

- **Roles**: `retail`, `wholesale_level1-3`, `trainer`, `federation_rep`, `admin`.
- **B2B Fields**: `company_name`, `tax_id`, `is_verified`.
- **1C Integration**: `onec_id`, `onec_guid`, `sync_status`.

### `Company`

B2B company details.

- **Fields**: `legal_name`, `tax_id`, `kpp`, `bank_bik`, `account_number`.

### `Address`

Shipping and legal addresses.

- **Type**: `shipping` / `legal`.
- **Logic**: Supports `is_default` flag per type.

---

## Products (`apps.products.models`)

### `Product`

Core catalog item.

- **Relations**: `Brand`, `Category`.
- **Pricing**: Has `discount_percent` and `is_sale/is_promo` flags.
- **1C Integration**: `onec_id`, `parent_onec_id` (sync with goods.xml).
- **Hybrid Images**: `base_images` (JSON list from 1C).
- **VAT**: `vat_rate` from `goods.xml`; fallback source for variants when VAT is imported separately from offers.

### `ProductVariant` (SKU)

Specific variation (Size/Color).

- **Prices**: Stores 6 price types (`retail_price`, `opt1_price`, etc.).
- **Inventory**: `stock_quantity`, `reserved_quantity`.
- **1C**: `onec_id`, `sku`.
- **VAT/Warehouse**: `vat_rate`, `warehouse_id`, `warehouse_name`. `ProductVariant.vat_rate` is the primary catalog VAT source for order creation and export fallback.

### `Category`

Hierarchical category tree.

- **Fields**: `name`, `slug`, `parent`, `image`.

### `Brand`

Product manufacturer.

- **Fields**: `name`, `normalized_name` (deduplication), `logo`.

### `Attribute` & `AttributeValue`

EAV system for product properties.

- **Normalization**: `normalized_name`/`normalized_value` for deduplication.

---

## Others

- **Orders**: `Order`, `OrderItem` (Snapshot of product data). Orders use a client-facing master plus technical sub-orders for 1C. Sub-orders are grouped by `(vat_rate, warehouse_name)`; `Order.vat_group` is authoritative for document VAT, and `OrderItem.vat_rate` snapshots item VAT at checkout time.
- **Cart**: Redis-backed (No persistent model, serialized on the fly).
