-- Inventario para reparaciones:
--   * Catálogo de productos y existencias por ubicación (bodega, vehículo...).
--   * Movimientos de stock como libro contable: nunca se edita la cantidad sin un movimiento.
--   * Clientes y equipos instalados en cada cliente.
--   * Reparaciones sobre esos equipos y repuestos consumidos (descuentan stock).

CREATE TABLE products (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sku         text NOT NULL UNIQUE CHECK (char_length(sku) BETWEEN 1 AND 60),
    name        text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
    -- camara, dvr_nvr, fuente, cable, conector, disco, accesorio, otro...
    category    text NOT NULL CHECK (char_length(category) BETWEEN 1 AND 60),
    brand       text CHECK (char_length(brand) <= 100),
    model       text CHECK (char_length(model) <= 100),
    unit        text NOT NULL DEFAULT 'unidad' CHECK (char_length(unit) BETWEEN 1 AND 30),
    min_stock   integer NOT NULL DEFAULT 0 CHECK (min_stock >= 0),
    description text CHECK (char_length(description) <= 2000),
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX products_category_idx ON products (category) WHERE is_active;
CREATE INDEX products_search_idx ON products
    USING gin (to_tsvector('spanish', name || ' ' || coalesce(brand, '') || ' ' || coalesce(model, '') || ' ' || sku));

CREATE TABLE stock_locations (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL UNIQUE CHECK (char_length(name) BETWEEN 1 AND 100),
    kind       text NOT NULL DEFAULT 'warehouse' CHECK (kind IN ('warehouse', 'vehicle', 'other')),
    is_active  boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE stock_levels (
    product_id  uuid NOT NULL REFERENCES products (id) ON DELETE RESTRICT,
    location_id uuid NOT NULL REFERENCES stock_locations (id) ON DELETE RESTRICT,
    quantity    integer NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (product_id, location_id)
);

CREATE TABLE clients (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
    document_id text CHECK (char_length(document_id) <= 30),
    phone       text CHECK (char_length(phone) <= 30),
    email       text CHECK (char_length(email) <= 320),
    address     text CHECK (char_length(address) <= 300),
    notes       text CHECK (char_length(notes) <= 2000),
    created_by  uuid REFERENCES app_users (id) ON DELETE SET NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX clients_name_idx ON clients (lower(name));

CREATE TABLE installed_equipment (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id        uuid NOT NULL REFERENCES clients (id) ON DELETE RESTRICT,
    -- Enlace opcional al catálogo cuando el equipo salió de nuestro inventario.
    product_id       uuid REFERENCES products (id) ON DELETE SET NULL,
    equipment_type   text NOT NULL CHECK (char_length(equipment_type) BETWEEN 1 AND 60),
    brand            text CHECK (char_length(brand) <= 100),
    model            text CHECK (char_length(model) <= 100),
    serial_number    text CHECK (char_length(serial_number) <= 100),
    site_description text CHECK (char_length(site_description) <= 300),
    installed_on     date,
    status           text NOT NULL DEFAULT 'operational'
                     CHECK (status IN ('operational', 'in_repair', 'out_of_service', 'removed')),
    notes            text CHECK (char_length(notes) <= 2000),
    created_by       uuid REFERENCES app_users (id) ON DELETE SET NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX installed_equipment_client_idx ON installed_equipment (client_id);
CREATE UNIQUE INDEX installed_equipment_serial_idx
    ON installed_equipment (lower(brand), lower(serial_number)) WHERE serial_number IS NOT NULL;

CREATE TABLE repairs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           uuid NOT NULL REFERENCES clients (id) ON DELETE RESTRICT,
    equipment_id        uuid REFERENCES installed_equipment (id) ON DELETE RESTRICT,
    technician_id       uuid NOT NULL REFERENCES app_users (id) ON DELETE RESTRICT,
    -- Conversación del chatbot que originó o acompañó la reparación, si existe.
    conversation_id     uuid REFERENCES conversations (id) ON DELETE SET NULL,
    problem_description text NOT NULL CHECK (char_length(problem_description) BETWEEN 1 AND 4000),
    diagnosis           text CHECK (char_length(diagnosis) <= 4000),
    solution            text CHECK (char_length(solution) <= 4000),
    status              text NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'in_progress', 'resolved', 'cancelled')),
    opened_at           timestamptz NOT NULL DEFAULT now(),
    closed_at           timestamptz,
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CHECK ((status IN ('resolved', 'cancelled')) = (closed_at IS NOT NULL))
);

CREATE INDEX repairs_equipment_idx ON repairs (equipment_id, opened_at DESC);
CREATE INDEX repairs_client_idx ON repairs (client_id, opened_at DESC);
CREATE INDEX repairs_technician_idx ON repairs (technician_id, opened_at DESC);
CREATE INDEX repairs_open_idx ON repairs (opened_at DESC) WHERE status IN ('open', 'in_progress');

CREATE TABLE stock_movements (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id     uuid NOT NULL REFERENCES products (id) ON DELETE RESTRICT,
    location_id    uuid NOT NULL REFERENCES stock_locations (id) ON DELETE RESTRICT,
    quantity_delta integer NOT NULL CHECK (quantity_delta <> 0),
    -- receipt: entrada de compra; issue: salida manual; adjustment: conteo físico;
    -- repair: repuesto usado en reparación; transfer_in/out: traslado entre ubicaciones.
    reason         text NOT NULL
                   CHECK (reason IN ('receipt', 'issue', 'adjustment', 'repair', 'transfer_in', 'transfer_out')),
    repair_id      uuid REFERENCES repairs (id) ON DELETE RESTRICT,
    note           text CHECK (char_length(note) <= 500),
    created_by     uuid NOT NULL REFERENCES app_users (id) ON DELETE RESTRICT,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CHECK ((reason = 'repair') = (repair_id IS NOT NULL)),
    CHECK (reason NOT IN ('receipt', 'transfer_in') OR quantity_delta > 0),
    CHECK (reason NOT IN ('issue', 'repair', 'transfer_out') OR quantity_delta < 0)
);

CREATE INDEX stock_movements_product_idx ON stock_movements (product_id, created_at DESC);
CREATE INDEX stock_movements_repair_idx ON stock_movements (repair_id) WHERE repair_id IS NOT NULL;
