# 9. Схема Базы Данных

> **Стратегия миграций:** Проект использует Django ORM migrations (backend/apps/*/migrations/). Партиционирование таблицы `orders_order` описано концептуально и пока не реализовано в миграциях — требует ручного SQL или кастомной миграции. Разработка и тестирование — через `--nomigrations` (создание схемы из моделей).

### Дизайн базы данных PostgreSQL

#### Основные таблицы

```sql
-- Users and Authentication
CREATE TABLE users_user (
    id SERIAL PRIMARY KEY,
    email VARCHAR(254) UNIQUE NOT NULL,
    first_name VARCHAR(150),
    last_name VARCHAR(150),
    phone VARCHAR(20),
    role VARCHAR(20) DEFAULT 'retail',
    company_name VARCHAR(200),
    tax_id VARCHAR(50),
    is_active BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users_user(email);
CREATE INDEX idx_users_role ON users_user(role);
CREATE INDEX idx_users_company ON users_user(company_name) WHERE company_name IS NOT NULL;

-- Company (B2B requisites)
CREATE TABLE users_company (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
    legal_name VARCHAR(255),
    tax_id VARCHAR(12),
    kpp VARCHAR(9),
    legal_address TEXT,
    bank_name VARCHAR(200),
    bank_bik VARCHAR(9),
    account_number VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_company_user ON users_company(user_id);

-- Brands
CREATE TABLE products_brand (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    logo VARCHAR(255),
    description TEXT,
    website VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Categories with hierarchical structure
CREATE TABLE products_category (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    parent_id INTEGER REFERENCES products_category(id),
    description TEXT,
    image VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    seo_title VARCHAR(200),
    seo_description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Banners for Hero Section
CREATE TABLE banners (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    subtitle VARCHAR(500),
    image VARCHAR(255) NOT NULL,
    image_alt VARCHAR(255),
    cta_text VARCHAR(50),
    cta_link VARCHAR(200),

    -- Targeting
    show_to_guests BOOLEAN DEFAULT FALSE,
    show_to_authenticated BOOLEAN DEFAULT FALSE,
    show_to_trainers BOOLEAN DEFAULT FALSE,
    show_to_wholesale BOOLEAN DEFAULT FALSE,
    show_to_federation BOOLEAN DEFAULT FALSE,

    -- Management
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    start_date TIMESTAMP WITH TIME ZONE,
    end_date TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_banners_active ON banners(is_active) WHERE is_active = true;
CREATE INDEX idx_banners_priority ON banners(priority);
CREATE INDEX idx_banners_dates ON banners(start_date, end_date);

-- Master Product table (parent entity, aggregates variants)
CREATE TABLE products_product (
    id SERIAL PRIMARY KEY,
    name VARCHAR(300) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    brand_id INTEGER NOT NULL REFERENCES products_brand(id),
    category_id INTEGER NOT NULL REFERENCES products_category(id),
    description TEXT,
    short_description TEXT,
    specifications JSONB DEFAULT '{}',
    base_images JSONB DEFAULT '[]',

    -- Marketing flags
    is_active BOOLEAN DEFAULT TRUE,
    is_hit BOOLEAN DEFAULT FALSE,
    is_new BOOLEAN DEFAULT FALSE,
    is_sale BOOLEAN DEFAULT FALSE,
    is_promo BOOLEAN DEFAULT FALSE,
    is_premium BOOLEAN DEFAULT FALSE,
    discount_percent DECIMAL(5,2) DEFAULT 0,

    -- Integration & Timestamps
    onec_id VARCHAR(100) UNIQUE,
    parent_onec_id VARCHAR(100),
    vat_rate DECIMAL(5,2),
    onec_brand_id VARCHAR(100),
    sync_status VARCHAR(20) DEFAULT 'pending',
    last_sync_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Product Variant table (SKU-level: pricing, inventory, warehouse)
CREATE TABLE products_productvariant (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products_product(id) ON DELETE CASCADE,
    sku VARCHAR(100) UNIQUE NOT NULL,
    onec_id VARCHAR(100) UNIQUE,

    -- Variant attributes
    color_name VARCHAR(100),
    size_value VARCHAR(50),

    -- Multi-tier pricing structure
    retail_price DECIMAL(10,2) NOT NULL,
    opt1_price DECIMAL(10,2),
    opt2_price DECIMAL(10,2),
    opt3_price DECIMAL(10,2),
    trainer_price DECIMAL(10,2),
    federation_price DECIMAL(10,2),

    -- Reference prices (B2B)
    rrp DECIMAL(10,2),
    msrp DECIMAL(10,2),

    -- VAT
    vat_rate DECIMAL(5,2),

    -- Warehouse
    warehouse_id VARCHAR(64),
    warehouse_name VARCHAR(255),

    -- Inventory
    stock_quantity INTEGER DEFAULT 0,
    reserved_quantity INTEGER DEFAULT 0,

    -- Images
    main_image VARCHAR(500),
    gallery_images JSONB DEFAULT '[]',

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Timestamps
    last_sync_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_stock_non_negative CHECK (stock_quantity >= 0)
);

-- Orders with time-based partitioning
CREATE TABLE orders_order (
    id SERIAL,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users_user(id),

    -- Customer info for guest orders
    customer_name VARCHAR(200),
    customer_email VARCHAR(254),
    customer_phone VARCHAR(20),

    -- Order details
    status VARCHAR(50) DEFAULT 'pending',
    total_amount DECIMAL(10,2) NOT NULL,
    discount_amount DECIMAL(10,2) DEFAULT 0,
    delivery_cost DECIMAL(10,2) DEFAULT 0,

    -- Delivery
    delivery_address TEXT NOT NULL,
    delivery_method VARCHAR(50),
    delivery_date DATE,

    -- Payment
    payment_method VARCHAR(50),
    payment_status VARCHAR(50) DEFAULT 'pending',
    payment_id VARCHAR(100),

    -- B2B specific
    company_name VARCHAR(200),
    tax_id VARCHAR(50),
    purchase_order_number VARCHAR(100),

    -- Integration & audit
    onec_id VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Order Items с композитным FOREIGN KEY для секционированных таблиц
CREATE TABLE orders_orderitem (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    order_created_at TIMESTAMP WITH TIME ZONE NOT NULL, -- Обязательно для FOREIGN KEY
    product_id INTEGER NOT NULL REFERENCES products_product(id),
    variant_id INTEGER REFERENCES products_productvariant(id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL,

    -- Snapshot of product data at time of order
    product_name VARCHAR(300) NOT NULL,
    product_sku VARCHAR(100) NOT NULL,

    -- Композитный FOREIGN KEY включающий partition key
    FOREIGN KEY (order_id, order_created_at) REFERENCES orders_order(id, created_at) ON DELETE CASCADE,

    CONSTRAINT chk_positive_quantity CHECK (quantity > 0),
    CONSTRAINT chk_positive_prices CHECK (unit_price > 0 AND total_price > 0)
);

-- Shopping Cart
CREATE TABLE cart_cart (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users_user(id),
    session_key VARCHAR(100),  -- For guest users
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE cart_cartitem (
    id SERIAL PRIMARY KEY,
    cart_id INTEGER NOT NULL REFERENCES cart_cart(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products_product(id),
    variant_id INTEGER REFERENCES products_productvariant(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(cart_id, variant_id),
    CONSTRAINT chk_positive_quantity CHECK (quantity > 0)
);
```

#### Индексы для производительности

```sql
-- Product search and filtering indexes
CREATE INDEX idx_products_brand ON products_product(brand_id);
CREATE INDEX idx_products_category ON products_product(category_id);
CREATE INDEX idx_products_active ON products_product(is_active) WHERE is_active = true;
CREATE INDEX idx_products_featured ON products_product(is_hit) WHERE is_hit = true;
CREATE INDEX idx_products_search ON products_product USING gin(search_vector);
CREATE INDEX idx_products_onec ON products_product(onec_id) WHERE onec_id IS NOT NULL;

-- Product variant indexes
CREATE INDEX idx_variants_product ON products_productvariant(product_id);
CREATE INDEX idx_variants_sku ON products_productvariant(sku);
CREATE INDEX idx_variants_onec ON products_productvariant(onec_id) WHERE onec_id IS NOT NULL;
CREATE INDEX idx_variants_stock ON products_productvariant(stock_quantity) WHERE stock_quantity > 0;
CREATE INDEX idx_variants_warehouse ON products_productvariant(warehouse_id) WHERE warehouse_id IS NOT NULL;
CREATE INDEX idx_variants_price_retail ON products_productvariant(retail_price);

-- Order indexes
CREATE INDEX idx_orders_user ON orders_order(user_id);
CREATE INDEX idx_orders_status ON orders_order(status);
CREATE INDEX idx_orders_payment ON orders_order(payment_id) WHERE payment_id IS NOT NULL;
CREATE INDEX idx_orders_created ON orders_order(created_at);
CREATE INDEX idx_orders_onec ON orders_order(onec_id) WHERE onec_id IS NOT NULL;

-- Order items indexes (включая order_created_at для эффективного JOIN)
CREATE INDEX idx_orderitems_order_composite ON orders_orderitem(order_id, order_created_at);
CREATE INDEX idx_orderitems_product ON orders_orderitem(product_id);

-- Cart indexes
CREATE INDEX idx_cart_user ON cart_cart(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_cart_session ON cart_cart(session_key) WHERE session_key IS NOT NULL;
CREATE INDEX idx_cartitems_cart ON cart_cartitem(cart_id);
CREATE INDEX idx_cartitems_product ON cart_cartitem(product_id);

-- Category hierarchy indexes
CREATE INDEX idx_categories_parent ON products_category(parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX idx_categories_active ON products_category(is_active) WHERE is_active = true;
```

#### Полнотекстовый поиск

```sql
-- Full-Text Search Configuration
CREATE TEXT SEARCH CONFIGURATION russian_products (COPY = russian);

-- Update search vector trigger (on master Product table)
CREATE OR REPLACE FUNCTION update_product_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('russian_products', COALESCE(NEW.name, '')), 'A') ||
        setweight(to_tsvector('russian_products', COALESCE(NEW.description, '')), 'B') ||
        setweight(to_tsvector('russian_products', COALESCE(NEW.short_description, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_product_search
    BEFORE INSERT OR UPDATE ON products_product
    FOR EACH ROW EXECUTE FUNCTION update_product_search_vector();
```

#### Секционирование для масштабируемости

```sql
-- Create partitions for orders table (by month)
CREATE TABLE orders_order_2024_01 PARTITION OF orders_order
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE orders_order_2024_02 PARTITION OF orders_order
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
-- ... continue for other months

-- Automatic partition creation function
CREATE OR REPLACE FUNCTION create_monthly_partition()
RETURNS void AS $$
DECLARE
    start_date DATE;
    end_date DATE;
    partition_name TEXT;
BEGIN
    start_date := date_trunc('month', NOW());
    end_date := start_date + INTERVAL '1 month';
    partition_name := 'orders_order_' || to_char(start_date, 'YYYY_MM');

    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF orders_order
                    FOR VALUES FROM (%L) TO (%L)',
                   partition_name, start_date, end_date);
END;
$$ LANGUAGE plpgsql;
```

#### Специальные таблицы для ФЗ-152 соответствия

```sql
-- Personal data audit log (ФЗ-152 compliance)
CREATE TABLE compliance_personaldatalog (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users_user(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    data_type VARCHAR(100) NOT NULL,
    processed_data JSONB,
    purpose VARCHAR(200),
    legal_basis VARCHAR(200),
    ip_address INET,
    user_agent TEXT,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_required_fields CHECK (
        action IS NOT NULL AND
        data_type IS NOT NULL AND
        processed_at IS NOT NULL
    )
);

-- Consent management for GDPR/ФЗ-152
CREATE TABLE compliance_consent (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
    consent_type VARCHAR(100) NOT NULL,
    is_given BOOLEAN NOT NULL DEFAULT false,
    given_at TIMESTAMP WITH TIME ZONE,
    withdrawn_at TIMESTAMP WITH TIME ZONE,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(user_id, consent_type)
);

-- Sync logs for 1C integration monitoring
CREATE TABLE integrations_synclog (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    records_processed INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    error_details JSONB DEFAULT '[]',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT chk_status CHECK (status IN ('started', 'completed', 'failed'))
);

CREATE INDEX idx_synclog_type_status ON integrations_synclog(sync_type, status);
CREATE INDEX idx_synclog_started ON integrations_synclog(started_at);
```

#### Хранимые процедуры для бизнес-логики

```sql
-- Function to get price by user role (from ProductVariant)
CREATE OR REPLACE FUNCTION get_user_price(
    p_variant_id INTEGER,
    p_user_role VARCHAR(20)
) RETURNS DECIMAL(10,2) AS $$
DECLARE
    variant_record RECORD;
    result_price DECIMAL(10,2);
BEGIN
    SELECT * INTO variant_record
    FROM products_productvariant
    WHERE id = p_variant_id AND is_active = true;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Product variant not found or inactive: %', p_variant_id;
    END IF;

    result_price := CASE p_user_role
        WHEN 'retail' THEN variant_record.retail_price
        WHEN 'wholesale_level1' THEN COALESCE(variant_record.opt1_price, variant_record.retail_price)
        WHEN 'wholesale_level2' THEN COALESCE(variant_record.opt2_price, variant_record.retail_price)
        WHEN 'wholesale_level3' THEN COALESCE(variant_record.opt3_price, variant_record.retail_price)
        WHEN 'trainer' THEN COALESCE(variant_record.trainer_price, variant_record.retail_price)
        WHEN 'federation_rep' THEN COALESCE(variant_record.federation_price, variant_record.retail_price)
        ELSE variant_record.retail_price
    END;

    RETURN result_price;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to calculate order total with user-specific pricing
CREATE OR REPLACE FUNCTION calculate_order_total(
    p_user_id INTEGER,
    p_cart_items JSONB
) RETURNS DECIMAL(10,2) AS $$
DECLARE
    user_role VARCHAR(20);
    item JSONB;
    total_amount DECIMAL(10,2) := 0;
    item_price DECIMAL(10,2);
BEGIN
    -- Get user role
    SELECT role INTO user_role FROM users_user WHERE id = p_user_id;

    -- Calculate total for each item
    FOR item IN SELECT * FROM jsonb_array_elements(p_cart_items)
    LOOP
        item_price := get_user_price(
            (item->>'variant_id')::INTEGER,
            user_role
        );

        total_amount := total_amount + (item_price * (item->>'quantity')::INTEGER);
    END LOOP;

    RETURN total_amount;
END;
$$ LANGUAGE plpgsql STABLE;
```

#### Важные архитектурные решения

**1. Двухмодельная структура продуктов (Product + ProductVariant):**

- `products_product` — master-запись товара (общие данные, описание, изображения, маркетинговые флаги)
- `products_productvariant` — SKU-уровень (ценообразование, остатки, склад, атрибуты варианта)
- Гостевая связь: `Product → ProductVariant` (OneToMany) — один товар может иметь множество торговых предложений
- Ценообразование и остатки хранятся на уровне варианта, а не товара
- Изображения: Product имеет `base_images` (fallback), ProductVariant — `main_image` и `gallery_images`

**2. Композитный FOREIGN KEY для секционированных таблиц:**

- `orders_orderitem` включает `order_created_at` для корректной работы с секционированной `orders_order`
- Это обеспечивает referential integrity на уровне БД

**3. Секционирование:**

- `orders_order` - по range от `created_at` для эффективного архивирования

**4. Ценообразование:**

- Multi-tier pricing на уровне ProductVariant с поддержкой всех типов пользователей
- RRP/MSRP поля для B2B пользователей (требование FR5)

**5. Соответствие ФЗ-152:**

- Audit log с `ON DELETE SET NULL` для сохранения аудита
- Система согласий (consent management)

---
