import { useState } from "react";
import type { FormEvent } from "react";

import {
  EmptyState, Field, LOCATION_KIND_LABEL, MOVEMENT_REASON_LABEL, Notice, formatDate, optional, useAction, useLoader,
} from "../components/ui";
import {
  createLocation, createProduct, listLocations, listMovements, listProducts, registerMovement, transferStock,
} from "../services/inventory";
import type { Account, LocationKind, ManualMovementReason, Product, StockLocation } from "../types/inventory";

interface Props { token: string; account: Account }

export function InventoryPage({ token, account }: Props) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [lowOnly, setLowOnly] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [panel, setPanel] = useState<"none" | "product" | "locations">("none");
  const isAdmin = account.role === "admin";

  const products = useLoader(() => listProducts(token, { q: search, low_stock: lowOnly }), [token, search, lowOnly]);
  const locations = useLoader(() => listLocations(token), [token]);
  const selected = products.data?.find((item) => item.id === selectedId) ?? null;

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    setSearch(query.trim());
  }

  return (
    <section className="module" aria-labelledby="inventory-title">
      <header className="module-header">
        <div>
          <span className="workspace-eyebrow">DISPONIBILIDAD EN TIEMPO REAL</span>
          <h1 id="inventory-title">Inventario</h1>
        </div>
        {isAdmin && (
          <div className="module-actions">
            <button className="btn" type="button" onClick={() => setPanel(panel === "locations" ? "none" : "locations")}>Ubicaciones</button>
            <button className="btn btn--primary" type="button" onClick={() => setPanel(panel === "product" ? "none" : "product")}>＋ Nuevo producto</button>
          </div>
        )}
      </header>

      {panel === "product" && <ProductForm token={token} onDone={() => { setPanel("none"); void products.reload(); }} />}
      {panel === "locations" && <LocationsPanel token={token} locations={locations.data ?? []} onChanged={() => void locations.reload()} />}

      <form className="toolbar" onSubmit={submitSearch} role="search">
        <input className="input" type="search" placeholder="Buscar por nombre, SKU, marca o modelo…" value={query}
          onChange={(event) => setQuery(event.target.value)} aria-label="Buscar productos" maxLength={100} />
        <button className="btn" type="submit">Buscar</button>
        <label className="check"><input type="checkbox" checked={lowOnly} onChange={(event) => setLowOnly(event.target.checked)} /> Solo bajo stock</label>
      </form>

      {products.error && <Notice kind="error">{products.error}</Notice>}

      <div className="split">
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Producto</th><th>Categoría</th><th className="num">Total</th><th>Dónde hay</th></tr></thead>
            <tbody>
              {products.data?.map((product) => (
                <tr key={product.id} className={product.id === selectedId ? "row--active" : undefined}
                  onClick={() => setSelectedId(product.id)} tabIndex={0}
                  onKeyDown={(event) => { if (event.key === "Enter") setSelectedId(product.id); }}>
                  <td><strong>{product.name}</strong><small>{product.sku}{product.brand ? ` · ${product.brand}` : ""}{product.model ? ` ${product.model}` : ""}</small></td>
                  <td>{product.category}</td>
                  <td className="num">
                    <span className={product.is_low_stock ? "qty qty--low" : "qty"}>{product.total_quantity}</span>
                    {product.is_low_stock && <small className="low-flag">bajo (mín. {product.min_stock})</small>}
                  </td>
                  <td>{product.stock.length === 0 ? <span className="muted">Sin existencias</span>
                    : product.stock.map((s) => <span className="chip" key={s.location_id}>{s.location_name}: {s.quantity}</span>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {products.loading && <EmptyState>Cargando productos…</EmptyState>}
          {!products.loading && products.data?.length === 0 && <EmptyState>No hay productos que coincidan.</EmptyState>}
        </div>

        <aside className="detail">
          {selected
            ? <ProductDetail key={selected.id} token={token} product={selected} isAdmin={isAdmin}
                locations={locations.data ?? []} onChanged={() => void products.reload()} />
            : <EmptyState>Selecciona un producto para ver su disponibilidad y movimientos.</EmptyState>}
        </aside>
      </div>
    </section>
  );
}

function ProductForm({ token, onDone }: { token: string; onDone: () => void }) {
  const action = useAction();
  const [form, setForm] = useState({ sku: "", name: "", category: "", brand: "", model: "", unit: "unidad", min_stock: "0", description: "" });
  const set = (key: keyof typeof form) => (event: { target: { value: string } }) => setForm({ ...form, [key]: event.target.value });

  async function submit(event: FormEvent) {
    event.preventDefault();
    const ok = await action.run(() => createProduct(token, {
      sku: form.sku.trim(), name: form.name.trim(), category: form.category.trim().toLowerCase(),
      brand: optional(form.brand), model: optional(form.model), unit: form.unit.trim() || "unidad",
      min_stock: Number(form.min_stock) || 0, description: optional(form.description),
    }));
    if (ok) onDone();
  }

  return (
    <form className="card form-grid" onSubmit={submit}>
      <h2 className="card-title">Nuevo producto</h2>
      <Field label="SKU / código"><input className="input" required maxLength={60} value={form.sku} onChange={set("sku")} /></Field>
      <Field label="Nombre"><input className="input" required maxLength={200} value={form.name} onChange={set("name")} /></Field>
      <Field label="Categoría"><input className="input" required maxLength={60} list="product-categories" placeholder="camara, dvr, fuente…" value={form.category} onChange={set("category")} /></Field>
      <datalist id="product-categories">{["camara", "dvr_nvr", "fuente", "cable", "conector", "disco", "accesorio"].map((c) => <option key={c} value={c} />)}</datalist>
      <Field label="Marca"><input className="input" maxLength={100} value={form.brand} onChange={set("brand")} /></Field>
      <Field label="Modelo"><input className="input" maxLength={100} value={form.model} onChange={set("model")} /></Field>
      <Field label="Unidad"><input className="input" maxLength={30} value={form.unit} onChange={set("unit")} /></Field>
      <Field label="Stock mínimo"><input className="input" type="number" min={0} value={form.min_stock} onChange={set("min_stock")} /></Field>
      <Field label="Descripción" wide><input className="input" maxLength={2000} value={form.description} onChange={set("description")} /></Field>
      {action.error && <Notice kind="error">{action.error}</Notice>}
      <div className="form-actions"><button className="btn btn--primary" disabled={action.busy}>{action.busy ? "Guardando…" : "Crear producto"}</button></div>
    </form>
  );
}

function LocationsPanel({ token, locations, onChanged }: { token: string; locations: StockLocation[]; onChanged: () => void }) {
  const action = useAction();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<LocationKind>("warehouse");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (await action.run(() => createLocation(token, { name: name.trim(), kind }), "Ubicación creada.")) {
      setName(""); onChanged();
    }
  }

  return (
    <div className="card">
      <h2 className="card-title">Ubicaciones de stock</h2>
      <div className="chips">{locations.length === 0 ? <span className="muted">Aún no hay ubicaciones.</span>
        : locations.map((l) => <span className="chip" key={l.id}>{l.name} <small>{LOCATION_KIND_LABEL[l.kind]}</small></span>)}</div>
      <form className="inline-form" onSubmit={submit}>
        <input className="input" required maxLength={100} placeholder="Ej. Bodega principal, Camioneta 2" value={name} onChange={(e) => setName(e.target.value)} aria-label="Nombre de la ubicación" />
        <select className="input" value={kind} onChange={(e) => setKind(e.target.value as LocationKind)} aria-label="Tipo de ubicación">
          {Object.entries(LOCATION_KIND_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <button className="btn" disabled={action.busy}>Agregar</button>
      </form>
      {action.error && <Notice kind="error">{action.error}</Notice>}
      {action.success && <Notice kind="success">{action.success}</Notice>}
    </div>
  );
}

function ProductDetail({ token, product, isAdmin, locations, onChanged }: {
  token: string; product: Product; isAdmin: boolean; locations: StockLocation[]; onChanged: () => void;
}) {
  const movements = useLoader(() => listMovements(token, product.id, 20), [token, product.id, product.total_quantity]);

  return (
    <div className="detail-body">
      <span className="workspace-eyebrow">{product.sku}</span>
      <h2 className="detail-title">{product.name}</h2>
      <p className="muted">{[product.brand, product.model].filter(Boolean).join(" ") || "Sin marca/modelo"} · {product.unit}</p>
      {product.description && <p>{product.description}</p>}

      <h3 className="section-title">Disponibilidad</h3>
      <dl className="stock-list">
        {product.stock.length === 0 && <dd className="muted">Sin existencias en ninguna ubicación.</dd>}
        {product.stock.map((s) => <div key={s.location_id}><dt>{s.location_name}</dt><dd>{s.quantity}</dd></div>)}
        <div className="stock-total"><dt>Total</dt><dd className={product.is_low_stock ? "qty--low" : undefined}>{product.total_quantity}</dd></div>
      </dl>

      {isAdmin && <MovementForm token={token} product={product} locations={locations} onDone={() => { onChanged(); void movements.reload(); }} />}

      <h3 className="section-title">Últimos movimientos</h3>
      {movements.error && <Notice kind="error">{movements.error}</Notice>}
      <ul className="timeline">
        {movements.data?.map((m) => (
          <li key={m.id}>
            <span className={m.quantity_delta > 0 ? "delta delta--in" : "delta delta--out"}>{m.quantity_delta > 0 ? "+" : ""}{m.quantity_delta}</span>
            <div><strong>{MOVEMENT_REASON_LABEL[m.reason] ?? m.reason}</strong> · {m.location_name}
              <small>{formatDate(m.created_at, true)} · {m.created_by_email}{m.note ? ` · ${m.note}` : ""}</small></div>
          </li>
        ))}
        {movements.data?.length === 0 && <li className="muted">Sin movimientos todavía.</li>}
      </ul>
    </div>
  );
}

function MovementForm({ token, product, locations, onDone }: {
  token: string; product: Product; locations: StockLocation[]; onDone: () => void;
}) {
  const action = useAction();
  const [mode, setMode] = useState<ManualMovementReason | "transfer">("receipt");
  const [chosenLocation, setLocationId] = useState("");
  // Si las ubicaciones llegan después de montar el formulario, se usa la primera.
  const locationId = chosenLocation || locations[0]?.id || "";
  const [targetId, setTargetId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [note, setNote] = useState("");

  if (locations.length === 0) return <Notice kind="error">Crea primero una ubicación (botón «Ubicaciones»).</Notice>;

  async function submit(event: FormEvent) {
    event.preventDefault();
    const amount = Number(quantity);
    const ok = await action.run(() => mode === "transfer"
      ? transferStock(token, { product_id: product.id, from_location_id: locationId, to_location_id: targetId, quantity: amount, note: optional(note) })
      : registerMovement(token, { product_id: product.id, location_id: locationId, reason: mode, quantity: amount, note: optional(note) }),
    "Movimiento registrado.");
    if (ok) { setNote(""); onDone(); }
  }

  return (
    <form className="card card--compact" onSubmit={submit}>
      <div className="segmented" role="radiogroup" aria-label="Tipo de movimiento">
        {(["receipt", "issue", "adjustment", "transfer"] as const).map((value) => (
          <button key={value} type="button" role="radio" aria-checked={mode === value}
            className={mode === value ? "segmented-on" : undefined} onClick={() => setMode(value)}>
            {value === "transfer" ? "Traslado" : MOVEMENT_REASON_LABEL[value]}
          </button>
        ))}
      </div>
      <div className="form-grid form-grid--tight">
        <Field label={mode === "transfer" ? "Desde" : "Ubicación"}>
          <select className="input" value={locationId} onChange={(e) => setLocationId(e.target.value)}>
            {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </Field>
        {mode === "transfer" && (
          <Field label="Hacia">
            <select className="input" required value={targetId} onChange={(e) => setTargetId(e.target.value)}>
              <option value="">Elige…</option>
              {locations.filter((l) => l.id !== locationId).map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </Field>
        )}
        <Field label={mode === "adjustment" ? "Cantidad contada" : "Cantidad"}>
          <input className="input" type="number" min={mode === "adjustment" ? 0 : 1} required value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        </Field>
        <Field label="Nota" wide><input className="input" maxLength={500} placeholder="Factura, motivo, conteo…" value={note} onChange={(e) => setNote(e.target.value)} /></Field>
      </div>
      {action.error && <Notice kind="error">{action.error}</Notice>}
      {action.success && <Notice kind="success">{action.success}</Notice>}
      <div className="form-actions"><button className="btn btn--primary" disabled={action.busy}>{action.busy ? "Guardando…" : "Registrar"}</button></div>
    </form>
  );
}
