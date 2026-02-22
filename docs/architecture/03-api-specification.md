# 3. Спецификация API

## Структура схемы OpenAPI 3.1

```yaml
openapi:
info:
  title: FREESPORT API
  description: Comprehensive e-commerce API supporting B2B/B2C operations
  version: "1.0.0"
  contact:
    name: FREESPORT Development Team
    email: dev@freesport.com

servers:
  - url: https://api.freesport.com/v1
    description: Production server
  - url: https://staging-api.freesport.com/v1
    description: Staging server

security:
  - BearerAuth: []
  - ApiKeyAuth: []

paths:
  # Authentication Endpoints
  /auth/register/:
    post:
      tags: [Authentication]
      summary: User registration
      description: Register new user. Tokens returned only for active users (Retail). B2B users require verification.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                email:
                  type: string
                  format: email
                password:
                  type: string
                  format: password
                first_name:
                  type: string
                last_name:
                  type: string
                role:
                  type: string
                  enum: [retail, wholesale_level1, trainer]
              required: [email, password, first_name, last_name, role]
      responses:
        '201':
          description: Registration successful
          content:
            application/json:
              schema:
                type: object
                properties:
                  message:
                    type: string
                  access:
                    type: string
                    description: Only for verified users
                  refresh:
                    type: string
                    description: Only for verified users
                  user:
                    $ref: '#/components/schemas/User'
        '400':
          description: Validation error

  /auth/login/:
    post:
      tags: [Authentication]
      summary: User login
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                email:
                  type: string
                  format: email
                password:
                  type: string
                  format: password
              required: [email, password]
      responses:
        '200':
          description: Login successful
          content:
            application/json:
              schema:
                type: object
                properties:
                  access_token:
                    type: string
                  refresh_token:
                    type: string
                  user:
                    $ref: '#/components/schemas/User'
        '401':
          description: Invalid credentials
        '403':
          description: Account pending verification (Epic 29.2)
          content:
            application/json:
              schema:
                type: object
                properties:
                  detail:
                    type: string
                    example: "Ваша учетная запись находится на проверке"
                  code:
                    type: string
                    example: "account_pending_verification"

  /auth/refresh/:
    post:
      tags: [Authentication]
      summary: Refresh access token
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                refresh_token:
                  type: string
              required: [refresh_token]

  # Product Catalog Endpoints  
  /products/:
    get:
      tags: [Products]
      summary: List products with filtering and pagination
      parameters:
        - name: category
          in: query
          schema:
            type: string
        - name: brand
          in: query
          schema:
            type: string
        - name: min_price
          in: query
          schema:
            type: number
        - name: max_price
          in: query
          schema:
            type: number
        - name: search
          in: query
          schema:
            type: string
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: page_size
          in: query
          schema:
            type: integer
            default: 20
            maximum: 100
      responses:
        '200':
          description: Products list
          content:
            application/json:
              schema:
                type: object
                properties:
                  count:
                    type: integer
                  next:
                    type: string
                    nullable: true
                  previous:
                    type: string
                    nullable: true
                  results:
                    type: array
                    items:
                      $ref: '#/components/schemas/Product'

  /products/{id}/:
    get:
      tags: [Products]
      summary: Get product details
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: integer
      responses:
        '200':
          description: Product details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProductDetail'

  # Catalog Filters (Story 14.3)
  /catalog/filters/:
    get:
      tags: [Catalog Filters]
      summary: Получение списка атрибутов для фильтрации товаров
      description: |
        Возвращает активные атрибуты с их значениями для построения UI фильтров в каталоге.
        Staff users могут использовать include_inactive=true для просмотра всех атрибутов.
      parameters:
        - name: include_inactive
          in: query
          description: Включить неактивные атрибуты (только для staff users)
          schema:
            type: boolean
            default: false
      responses:
        '200':
          description: Список атрибутов для фильтрации
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/AttributeFilter'

  # Banners API
  /banners/active/:
    get:
      tags: [Banners]
      summary: Получить активные баннеры для текущего пользователя
      description: |
        Возвращает список активных баннеров, отфильтрованных по роли пользователя.
        Для неавторизованных пользователей возвращаются баннеры с show_to_guests=true.
      security: []  # Опциональная авторизация
      responses:
        '200':
          description: Список баннеров
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Banner'

  # News API
  /news/:
    get:
      tags: [News]
      summary: Get list of published news
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: page_size
          in: query
          schema:
            type: integer
            default: 10
      responses:
        '200':
          description: News list
          content:
            application/json:
              schema:
                type: object
                properties:
                  count:
                    type: integer
                  next:
                    type: string
                    nullable: true
                  previous:
                    type: string
                    nullable: true
                  results:
                    type: array
                    items:
                      $ref: '#/components/schemas/News'

  /news/{slug}/:
    get:
      tags: [News]
      summary: Get news details by slug
      parameters:
        - name: slug
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: News details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/NewsDetail'
        '404':
          description: News not found

  # Blog API
  /blog/:
    get:
      tags: [Blog]
      summary: Get list of published blog posts
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: page_size
          in: query
          schema:
            type: integer
            default: 10
      responses:
        '200':
          description: Blog posts list
          content:
            application/json:
              schema:
                type: object
                properties:
                  count:
                    type: integer
                  next:
                    type: string
                    nullable: true
                  previous:
                    type: string
                    nullable: true
                  results:
                    type: array
                    items:
                      $ref: '#/components/schemas/BlogPost'

  /blog/{slug}/:
    get:
      tags: [Blog]
      summary: Get blog post details by slug
      parameters:
        - name: slug
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Blog post details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BlogPostDetail'
        '404':
          description: Blog post not found

  # Cart Management
  /cart/:
    get:
      tags: [Cart]
      summary: Get current user's cart
      security:
        - BearerAuth: []
      responses:
        '200':
          description: Cart contents
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Cart'
    
    post:
      tags: [Cart]
      summary: Add item to cart
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                product_id:
                  type: integer
                quantity:
                  type: integer
                  minimum: 1
              required: [product_id, quantity]

  # Order Management
  /orders/:
    get:
      tags: [Orders]
      summary: List user orders
      security:
        - BearerAuth: []
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [pending, confirmed, processing, shipped, delivered, cancelled]
        - name: page
          in: query
          schema:
            type: integer
      responses:
        '200':
          description: Orders list
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderList'
    
    post:
      tags: [Orders]
      summary: Create new order
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/OrderCreate'
      responses:
        '201':
          description: Order created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Order'

  # 1C Integration Endpoints
  /api/1c/customers/:
    get:
      tags: [1C Integration]
      summary: List customers for 1C sync
      security:
        - ApiKeyAuth: []
      parameters:
        - name: modified_since
          in: query
          description: Filter customers modified since timestamp
          schema:
            type: string
            format: date-time
        - name: sync_status
          in: query
          description: Filter by sync status
          schema:
            type: string
            enum: [pending, synced, error]
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: page_size
          in: query
          schema:
            type: integer
            default: 50
            maximum: 200
      responses:
        '200':
          description: Customers list for sync
          content:
            application/json:
              schema:
                type: object
                properties:
                  count:
                    type: integer
                  next:
                    type: string
                    nullable: true
                  previous:
                    type: string
                    nullable: true
                  results:
                    type: array
                    items:
                      $ref: '#/components/schemas/Customer1C'
    
    post:
      tags: [1C Integration]
      summary: Import customers from 1C
      security:
        - ApiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                customers:
                  type: array
                  items:
                    $ref: '#/components/schemas/Customer1CImport'
                sync_operation_id:
                  type: string
                  description: Unique identifier for sync operation
              required: [customers]
      responses:
        '202':
          description: Import initiated
          content:
            application/json:
              schema:
                type: object
                properties:
                  operation_id:
                    type: string
                  status:
                    type: string
                    enum: [initiated]
                  imported_count:
                    type: integer
                  conflicts_count:
                    type: integer
        '400':
          description: Bad request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

  /api/1c/customers/{onec_id}/:
    get:
      tags: [1C Integration]
      summary: Get customer by 1C ID
      security:
        - ApiKeyAuth: []
      parameters:
        - name: onec_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Customer found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Customer1C'
        '404':
          description: Customer not found
    
    put:
      tags: [1C Integration]
      summary: Update customer from 1C
      security:
        - ApiKeyAuth: []
      parameters:
        - name: onec_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Customer1CImport'
      responses:
        '200':
          description: Customer updated
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Customer1C'
        '409':
          description: Conflict detected
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SyncConflict'

  /api/1c/orders/:
    get:
      tags: [1C Integration]
      summary: Get orders for export to 1C
      security:
        - ApiKeyAuth: []
      parameters:
        - name: export_status
          in: query
          description: Filter by export status
          schema:
            type: string
            enum: [pending, exported, error]
        - name: created_since
          in: query
          description: Filter orders created since timestamp
          schema:
            type: string
            format: date-time
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: page_size
          in: query
          schema:
            type: integer
            default: 50
      responses:
        '200':
          description: Orders for export
          content:
            application/json:
              schema:
                type: object
                properties:
                  count:
                    type: integer
                  results:
                    type: array
                    items:
                      $ref: '#/components/schemas/Order1CExport'
    
    post:
      tags: [1C Integration]
      summary: Update order statuses from 1C
      security:
        - ApiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                orders:
                  type: array
                  items:
                    type: object
                    properties:
                      platform_order_id:
                        type: integer
                      onec_id:
                        type: string
                      status:
                        type: string
                        enum: [confirmed, processing, shipped, delivered, cancelled]
                      tracking_number:
                        type: string
                        nullable: true
                    required: [platform_order_id, status]
              required: [orders]
      responses:
        '200':
          description: Orders updated
          content:
            application/json:
              schema:
                type: object
                properties:
                  updated_count:
                    type: integer
                  errors:
                    type: array
                    items:
                      type: object
                      properties:
                        order_id:
                          type: integer
                        error:
                          type: string

  /api/1c/sync/conflicts/:
    get:
      tags: [1C Integration]
      summary: List sync conflicts
      security:
        - ApiKeyAuth: []
      parameters:
        - name: conflict_type
          in: query
          schema:
            type: string
            enum: [customer_data, product_data, order_status, pricing]
        - name: is_resolved
          in: query
          schema:
            type: boolean
        - name: page
          in: query
          schema:
            type: integer
            default: 1
      responses:
        '200':
          description: Conflicts list
          content:
            application/json:
              schema:
                type: object
                properties:
                  count:
                    type: integer
                  results:
                    type: array
                    items:
                      $ref: '#/components/schemas/SyncConflict'

  /api/1c/sync/conflicts/{conflict_id}/resolve/:
    post:
      tags: [1C Integration]
      summary: Resolve sync conflict
      security:
        - ApiKeyAuth: []
      parameters:
        - name: conflict_id
          in: path
          required: true
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                resolution_strategy:
                  type: string
                  enum: [platform_wins, onec_wins, merge, manual]
                resolution_details:
                  type: object
                  description: Details of manual resolution if strategy is manual
              required: [resolution_strategy]
      responses:
        '200':
          description: Conflict resolved
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SyncConflict'

  /api/1c/sync/logs/:
    get:
      tags: [1C Integration]
      summary: Get sync operation logs
      security:
        - ApiKeyAuth: []
      parameters:
        - name: operation_type
          in: query
          schema:
            type: string
            enum: [import_from_1c, export_to_1c, sync_changes]
        - name: status
          in: query
          schema:
            type: string
            enum: [success, error, skipped, conflict]
        - name: date_from
          in: query
          schema:
            type: string
            format: date-time
        - name: date_to
          in: query
          schema:
            type: string
            format: date-time
        - name: page
          in: query
          schema:
            type: integer
            default: 1
      responses:
        '200':
          description: Sync logs
          content:
            application/json:
              schema:
                type: object
                properties:
                  count:
                    type: integer
                  results:
                    type: array
                    items:
                      $ref: '#/components/schemas/CustomerSyncLog'

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key

  schemas:
    User:
      type: object
      properties:
        id:
          type: integer
        email:
          type: string
          format: email
        first_name:
          type: string
        last_name:
          type: string
        role:
          type: string
          enum: [retail, wholesale_level1, wholesale_level2, wholesale_level3, trainer, federation_rep, admin]
        company_name:
          type: string
          nullable: true
        is_verified_b2b:
          type: boolean
        created_at:
          type: string
          format: date-time

    Company:
      type: object
      description: Реквизиты компании для B2B пользователей
      properties:
        id:
          type: integer
        legal_name:
          type: string
          description: Юридическое название
        tax_id:
          type: string
          description: ИНН
        kpp:
          type: string
          description: КПП
        legal_address:
          type: string
          description: Юридический адрес
        bank_name:
          type: string
          description: Название банка
        bank_bik:
          type: string
          description: БИК банка
        account_number:
          type: string
          description: Расчётный счёт
        created_at:
          type: string

    Product:
      type: object
      properties:
        id:
          type: integer
        name:
          type: string
        slug:
          type: string
        article:
          type: string
        retail_price:
          type: number
          format: decimal
        current_user_price:
          type: number
          format: decimal
          description: Price based on user's role
        stock_quantity:
          type: integer
          description: "Общее физическое количество товара на складе."
        reserved_quantity:
          type: integer
          description: "Количество товара, зарезервированное в активных корзинах."
          readOnly: true
        available_quantity:
          type: integer
          description: "Доступное для заказа количество (stock_quantity - reserved_quantity)."
          readOnly: true
        is_available:
          type: boolean
          description: "Доступен ли товар для заказа в данный момент (is_active && available_quantity > 0)."
          readOnly: true
        brand:
          type: string
        category:
          type: string

    ProductDetail:
      allOf:
        - $ref: '#/components/schemas/Product'
        - type: object
          properties:
            description:
              type: string
            specifications:
              type: object
            opt1_price:
              type: number
            opt2_price:
              type: number
            opt3_price:
              type: number
            trainer_price:
              type: number
            federation_price:
              type: number

    # Catalog Filter Schemas (Story 14.3)
    AttributeFilter:
      type: object
      description: Атрибут для фильтрации товаров в каталоге
      properties:
        id:
          type: integer
        name:
          type: string
          description: Название атрибута
        slug:
          type: string
          description: URL-совместимый идентификатор
        values:
          type: array
          description: Список значений атрибута
          items:
            $ref: '#/components/schemas/AttributeValueFilter'

    AttributeValueFilter:
      type: object
      description: Значение атрибута для фильтра
      properties:
        id:
          type: integer
        value:
          type: string
          description: Отображаемое значение
        slug:
          type: string
          description: URL-совместимый идентификатор значения

    # News Schemas
    News:
      type: object
      properties:
        id:
          type: integer
        title:
          type: string
        slug:
          type: string
        short_description:
          type: string
        image:
          type: string
          format: uri
        published_at:
          type: string
          format: date-time

    NewsDetail:
      allOf:
        - $ref: '#/components/schemas/News'
        - type: object
          properties:
            content:
              type: string

    # Blog Schemas
    BlogPost:
      type: object
      properties:
        id:
          type: integer
        title:
          type: string
        slug:
          type: string
        subtitle:
          type: string
        excerpt:
          type: string
        image:
          type: string
          format: uri
        author:
          type: string
        category:
          type: object
          properties:
            id:
              type: integer
            name:
              type: string
            slug:
              type: string
          nullable: true
        published_at:
          type: string
          format: date-time

    BlogPostDetail:
      allOf:
        - $ref: '#/components/schemas/BlogPost'
        - type: object
          properties:
            content:
              type: string
            meta_title:
              type: string
            meta_description:
              type: string
            created_at:
              type: string
              format: date-time
            updated_at:
              type: string
              format: date-time

    # 1C Integration Schemas
    Customer1C:
      type: object
      properties:
        id:
          type: integer
        email:
          type: string
          format: email
        first_name:
          type: string
        last_name:
          type: string
        phone:
          type: string
        company_name:
          type: string
          nullable: true
        tax_id:
          type: string
          nullable: true
        legal_address:
          type: string
          nullable: true
        contact_person:
          type: string
          nullable: true
        role:
          type: string
          enum: [retail, wholesale_level1, wholesale_level2, wholesale_level3, trainer, federation_rep, admin]
        is_verified_b2b:
          type: boolean
        onec_id:
          type: string
          nullable: true
        onec_guid:
          type: string
          format: uuid
          nullable: true
        last_sync_from_1c:
          type: string
          format: date-time
          nullable: true
        last_sync_to_1c:
          type: string
          format: date-time
          nullable: true
        sync_conflicts:
          type: object
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    Customer1CImport:
      type: object
      properties:
        onec_id:
          type: string
        onec_guid:
          type: string
          format: uuid
        email:
          type: string
          format: email
        first_name:
          type: string
        last_name:
          type: string
        phone:
          type: string
          nullable: true
        company_name:
          type: string
          nullable: true
        tax_id:
          type: string
          nullable: true
        legal_address:
          type: string
          nullable: true
        contact_person:
          type: string
          nullable: true
        role:
          type: string
          enum: [retail, wholesale_level1, wholesale_level2, wholesale_level3, trainer, federation_rep, admin]
          default: retail
        is_verified_b2b:
          type: boolean
          default: false
        force_update:
          type: boolean
          default: false
          description: Force update even if conflicts exist
      required: [onec_id, email, first_name, last_name]

    Order1CExport:
      type: object
      properties:
        id:
          type: integer
        order_number:
          type: string
        customer:
          type: object
          properties:
            id:
              type: integer
            email:
              type: string
            onec_id:
              type: string
              nullable: true
            company_name:
              type: string
              nullable: true
            tax_id:
              type: string
              nullable: true
        status:
          type: string
          enum: [pending, confirmed, processing, shipped, delivered, cancelled, returned]
        total_amount:
          type: number
          format: decimal
        shipping_address:
          type: object
        items:
          type: array
          items:
            type: object
            properties:
              product_id:
                type: integer
              product_article:
                type: string
              product_name:
                type: string
              onec_product_id:
                type: string
                nullable: true
              quantity:
                type: integer
              unit_price:
                type: number
                format: decimal
              total_price:
                type: number
                format: decimal
        created_at:
          type: string
          format: date-time
        exported_to_1c:
          type: boolean
        onec_id:
          type: string
          nullable: true

    SyncConflict:
      type: object
      properties:
        id:
          type: integer
        conflict_type:
          type: string
          enum: [customer_data, product_data, order_status, pricing]
        customer_id:
          type: integer
          nullable: true
        product_id:
          type: integer
          nullable: true
        order_id:
          type: integer
          nullable: true
        platform_data:
          type: object
          description: Current data in the platform
        onec_data:
          type: object
          description: Data from 1C
        conflicting_fields:
          type: array
          items:
            type: string
          description: List of fields with conflicts
        resolution_strategy:
          type: string
          enum: [manual, platform_wins, onec_wins, merge]
        is_resolved:
          type: boolean
        resolution_details:
          type: object
        resolved_at:
          type: string
          format: date-time
          nullable: true
        resolved_by:
          type: string
          nullable: true
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    CustomerSyncLog:
      type: object
      properties:
        id:
          type: integer
        operation_type:
          type: string
          enum: [import_from_1c, export_to_1c, sync_changes]
        customer_id:
          type: integer
        status:
          type: string
          enum: [success, error, skipped, conflict]
        details:
          type: object
          description: Synchronization details
        changes_made:
          type: object
          description: Changes that were made
        conflict_resolution:
          type: object
          description: How conflicts were resolved
        error_message:
          type: string
          nullable: true
        created_at:
          type: string
          format: date-time
        processed_by:
          type: string
          description: Management command or user who initiated the operation

    Error:
      type: object
      properties:
        error:
          type: string
        message:
          type: string
        details:
          type: object
          nullable: true

    Cart:
      type: object
      properties:
        id:
          type: integer
        items:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              product:
                $ref: '#/components/schemas/Product'
              quantity:
                type: integer
              price_at_add:
                type: number
                format: decimal
        total_items:
          type: integer
        total_amount:
          type: number
          format: decimal

    Order:
      type: object
      properties:
        id:
          type: integer
        order_number:
          type: string
        status:
          type: string
          enum: [draft, pending, processing, shipped, delivered, cancelled, returned]
        total_amount:
          type: number
          format: decimal
        items:
          type: array
          items:
            type: object
            properties:
              product_name:
                type: string
              quantity:
                type: integer
              unit_price:
                type: number
              total_price:
                type: number
        created_at:
          type: string
          format: date-time

    OrderList:
      type: object
      properties:
        count:
          type: integer
        next:
          type: string
          nullable: true
        previous:
          type: string
          nullable: true
        results:
          type: array
          items:
            $ref: '#/components/schemas/Order'

    OrderCreate:
      type: object
      properties:
        shipping_address:
          type: object
          properties:
            full_name:
              type: string
            phone:
              type: string
            city:
              type: string
            street:
              type: string
            building:
              type: string
            apartment:
              type: string
            postal_code:
              type: string
          required: [full_name, phone, city, street, building]
        payment_method:
          type: string
        notes:
          type: string
          nullable: true
      required: [shipping_address, payment_method]
```

## Особенности API интеграции с 1С

### Аутентификация

- **JWT Bearer Token**: Для пользовательских операций
- **API Key**: Для интеграции с 1С системой

### Endpoints для синхронизации покупателей

- `GET /api/1c/customers/` - Получение списка покупателей для синхронизации
- `POST /api/1c/customers/` - Импорт покупателей из 1С
- `PUT /api/1c/customers/{onec_id}/` - Обновление конкретного покупателя
- `GET /api/1c/customers/{onec_id}/` - Получение покупателя по ID 1С

### Управление заказами

- `GET /api/1c/orders/` - Получение заказов для экспорта в 1С
- `POST /api/1c/orders/` - Обновление статусов заказов из 1С

### Управление конфликтами

- `GET /api/1c/sync/conflicts/` - Список конфликтов синхронизации
- `POST /api/1c/sync/conflicts/{id}/resolve/` - Разрешение конфликта

### Логирование и мониторинг

- `GET /api/1c/sync/logs/` - Получение логов операций синхронизации

### Коды ответов

- **200 OK**: Успешная операция
- **201 Created**: Ресурс создан
- **202 Accepted**: Операция принята к обработке (асинхронные операции)
- **400 Bad Request**: Некорректный запрос
- **401 Unauthorized**: Не авторизован
- **403 Forbidden**: Доступ запрещен
- **404 Not Found**: Ресурс не найден
- **409 Conflict**: Конфликт данных при синхронизации
- **500 Internal Server Error**: Внутренняя ошибка сервера

#### Pagination

Все endpoints с множественными результатами поддерживают pagination:

- `page`: номер страницы (по умолчанию 1)
- `page_size`: размер страницы (по умолчанию 20, максимум 200)

#### Фильтрация

Поддерживается фильтрация по:

- Времени модификации (`modified_since`, `created_since`)
- Статусу синхронизации (`sync_status`, `export_status`)
- Типу операции (`operation_type`, `conflict_type`)
- Статусу разрешения (`is_resolved`)
