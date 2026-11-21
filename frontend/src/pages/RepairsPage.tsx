import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  EmptyState, Field, Notice, REPAIR_STATUS_LABEL, StatusBadge, formatDate, optional, useAction, useLoader,
} from "../components/ui";
import {
  addRepairPart, getClient, getRepair, listClients, listProducts, listRepairs, openRepair, updateRepair,
} from "../services/inventory";
import type { Account, Product, RepairDetail, RepairStatus } from "../types/inventory";
import { equipmentLabel } from "./ClientsPage";

interface Props { token: string; account: Account; focusId: string | null; onFocus: (id: string | null) => void }

export function RepairsPage({ token, account, focusId, onFocus }: Props) {
  const [status, setStatus] = useState<RepairStatus | "">("");
  const [mine, setMine] = useState(account.role === "technician");
  const [creating, setCreating] = useState(false);
  const repairs = useLoader(() => listRepairs(token, { status, mine }), [token, status, mine]);

  return (
    <section className="module" aria-labelledby="repairs-title">
      <header className="module-header">
        <div>
          <span className="workspace-eyebrow">ÓRDENES DE SERVICIO</span>
          <h1 id="repairs-title">Reparaciones</h1>
        </div>
        <div className="module-actions">
          <button className="btn btn--primary" type="button" onClick={() => setCreating(!creating)}>＋ Nueva reparación</button>
        </div>
      </header>

      {creating && <NewRepairForm token={token} onDone={(id) => { setCreating(false); onFocus(id); void repairs.reload(); }} />}

      <div className="toolbar">
        <select className="input input--auto" value={status} onChange={(e) => setStatus(e.target.value as RepairStatus | "")} aria-label="Filtrar por estado">
          <option value="">Todos los estados</option>
          {Object.entries(REPAIR_STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <label className="check"><input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} /> Solo las mías</label>
      </div>
      {repairs.error && <Notice kind="error">{repairs.error}</Notice>}

      <div className="split">
        <div className="list">
          {repairs.data?.map((repair) => (
            <button key={repair.id} type="button" className={`list-item${repair.id === focusId ? " list-item--active" : ""}`}
              onClick={() => onFocus(repair.id)}>
              <span className="list-top"><strong>{repair.client_name}</strong><StatusBadge status={repair.status} label={REPAIR_STATUS_LABEL[repair.status]} /></span>
              <small>{repair.equipment_label ?? "Sin equipo asociado"} · {formatDate(repair.opened_at)}</small>
              <span className="list-meta">{repair.problem_description}</span>
            </button>
          ))}
          {repairs.loading && <EmptyState>Cargando reparaciones…</EmptyState>}
          {!repairs.loading && repairs.data?.length === 0 && <EmptyState>No hay reparaciones con estos filtros.</EmptyState>}
        </div>
        <aside className="detail">
          {focusId
            ? <RepairPanel key={focusId} token={token} account={account} repairId={focusId} onChanged={() => void repairs.reload()} />
            : <EmptyState>Selecciona una reparación para ver su detalle y registrar repuestos.</EmptyState>}
        </aside>
      </div>
    </section>
  );
}

function NewRepairForm({ token, onDone }: { token: string; onDone: (id: string) => void }) {
  const action = useAction();
  const clients = useLoader(() => listClients(token), [token]);
  const [clientId, setClientId] = useState("");
  const [equipmentId, setEquipmentId] = useState("");
  const [problem, setProblem] = useState("");
  const client = useLoader(() => clientId ? getClient(token, clientId) : Promise.resolve(null), [token, clientId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const result = { id: "" };
    const ok = await action.run(async () => {
      result.id = (await openRepair(token, {
        client_id: clientId, equipment_id: equipmentId || null, problem_description: problem.trim(),
      })).id;
    });
    if (ok) onDone(result.id);
  }

  return (
    <form className="card form-grid" onSubmit={submit}>
      <h2 className="card-title">Nueva reparación</h2>
      <Field label="Cliente">
        <select className="input" required value={clientId} onChange={(e) => { setClientId(e.target.value); setEquipmentId(""); }}>
          <option value="">Elige un cliente…</option>
          {clients.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </Field>
      <Field label="Equipo (opcional)">
        <select className="input" value={equipmentId} onChange={(e) => setEquipmentId(e.target.value)} disabled={!client.data}>
          <option value="">Sin equipo específico</option>
          {client.data?.equipment.filter((e) => e.status !== "removed").map((e) => (
            <option key={e.id} value={e.id}>{equipmentLabel(e)}{e.serial_number ? ` · S/N ${e.serial_number}` : ""}</option>
          ))}
        </select>
      </Field>
      <Field label="Falla reportada" wide>
        <textarea className="input" required maxLength={4000} rows={3} value={problem} onChange={(e) => setProblem(e.target.value)}
          placeholder="Qué reporta el cliente y qué observaste." />
      </Field>
      {clients.data?.length === 0 && <Notice kind="error">Primero registra el cliente en la sección Clientes.</Notice>}
      {action.error && <Notice kind="error">{action.error}</Notice>}
      <div className="form-actions"><button className="btn btn--primary" disabled={action.busy}>{action.busy ? "Abriendo…" : "Abrir reparación"}</button></div>
    </form>
  );
}

function RepairPanel({ token, account, repairId, onChanged }: {
  token: string; account: Account; repairId: string; onChanged: () => void;
}) {
  const repair = useLoader(() => getRepair(token, repairId), [token, repairId]);
  if (repair.loading && !repair.data) return <EmptyState>Cargando…</EmptyState>;
  if (repair.error || !repair.data) return <Notice kind="error">{repair.error ?? "No se encontró la reparación."}</Notice>;

  const data = repair.data;
  const closed = data.status === "resolved" || data.status === "cancelled";
  const canEdit = !closed && (account.role === "admin" || data.technician_id === account.id);
  const refresh = () => { void repair.reload(); onChanged(); };

  return (
    <div className="detail-body">
      <span className="workspace-eyebrow">REPARACIÓN · {formatDate(data.opened_at, true)}</span>
      <h2 className="detail-title">{data.client_name}</h2>
      <p className="muted">{data.equipment_label ?? "Sin equipo asociado"}{data.equipment_serial ? ` · S/N ${data.equipment_serial}` : ""}</p>
      <p><StatusBadge status={data.status} label={REPAIR_STATUS_LABEL[data.status]} /> <span className="muted">Técnico: {data.technician_name ?? data.technician_email}</span></p>

      <h3 className="section-title">Falla reportada</h3>
      <p className="prose">{data.problem_description}</p>

      {canEdit
        ? <RepairEditor token={token} repair={data} onSaved={refresh} />
        : <>
            <h3 className="section-title">Diagnóstico</h3><p className="prose">{data.diagnosis ?? "—"}</p>
            <h3 className="section-title">Solución</h3><p className="prose">{data.solution ?? "—"}</p>
            {closed && <p className="muted">Cerrada el {formatDate(data.closed_at, true)}.</p>}
            {!closed && <p className="muted">Solo el técnico asignado o un administrador puede modificarla.</p>}
          </>}

      <h3 className="section-title">Repuestos usados</h3>
      <ul className="timeline">
        {data.parts.length === 0 && <li className="muted">Ningún repuesto registrado.</li>}
        {data.parts.map((part) => (
          <li key={part.id}>
            <span className="delta delta--out">{-part.quantity_delta}</span>
            <div><strong>{part.product_name}</strong> · {part.location_name}
              <small>{part.product_sku} · {formatDate(part.created_at, true)} · {part.created_by_email}</small></div>
          </li>
        ))}
      </ul>
      {canEdit && <PartForm token={token} repairId={data.id} onAdded={refresh} />}
    </div>
  );
}

function RepairEditor({ token, repair, onSaved }: { token: string; repair: RepairDetail; onSaved: () => void }) {
  const action = useAction();
  const [diagnosis, setDiagnosis] = useState(repair.diagnosis ?? "");
  const [solution, setSolution] = useState(repair.solution ?? "");

  async function save(status?: RepairStatus) {
    const ok = await action.run(() => updateRepair(token, repair.id, {
      diagnosis: optional(diagnosis), solution: optional(solution), ...(status ? { status } : {}),
    }), status ? undefined : "Cambios guardados.");
    if (ok) onSaved();
  }

  return (
    <div className="card card--compact">
      <Field label="Diagnóstico" wide><textarea className="input" rows={3} maxLength={4000} value={diagnosis} onChange={(e) => setDiagnosis(e.target.value)} /></Field>
      <Field label="Solución aplicada" wide><textarea className="input" rows={3} maxLength={4000} value={solution} onChange={(e) => setSolution(e.target.value)} /></Field>
      {action.error && <Notice kind="error">{action.error}</Notice>}
      {action.success && <Notice kind="success">{action.success}</Notice>}
      <div className="form-actions">
        <button className="btn" type="button" disabled={action.busy} onClick={() => void save()}>Guardar</button>
        <button className="btn" type="button" disabled={action.busy} onClick={() => void save("cancelled")}>Cancelar reparación</button>
        <button className="btn btn--primary" type="button" disabled={action.busy || !solution.trim()}
          title={solution.trim() ? undefined : "Escribe la solución antes de cerrar"} onClick={() => void save("resolved")}>Marcar resuelta</button>
      </div>
    </div>
  );
}

function PartForm({ token, repairId, onAdded }: { token: string; repairId: string; onAdded: () => void }) {
  const action = useAction();
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [product, setProduct] = useState<Product | null>(null);
  const [locationId, setLocationId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const results = useLoader(() => search ? listProducts(token, { q: search }) : Promise.resolve([] as Product[]), [token, search]);

  // Por defecto, la ubicación con más existencias del producto elegido.
  useEffect(() => {
    const best = product?.stock.slice().sort((a, b) => b.quantity - a.quantity)[0];
    setLocationId(best?.location_id ?? "");
  }, [product]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!product) return;
    const ok = await action.run(() => addRepairPart(token, repairId, {
      product_id: product.id, location_id: locationId, quantity: Number(quantity),
    }), "Repuesto registrado y descontado del inventario.");
    if (ok) { setProduct(null); setQuery(""); setSearch(""); setQuantity("1"); onAdded(); }
  }

  return (
    <div className="card card--compact">
      <h4>Agregar repuesto</h4>
      {!product && (
        <form className="inline-form" onSubmit={(e) => { e.preventDefault(); setSearch(query.trim()); }}>
          <input className="input" type="search" placeholder="Buscar repuesto (nombre, SKU, marca)…" value={query}
            onChange={(e) => setQuery(e.target.value)} aria-label="Buscar repuesto" />
          <button className="btn">Buscar</button>
        </form>
      )}
      {!product && results.data && results.data.length > 0 && (
        <ul className="pick-list">
          {results.data.map((item) => (
            <li key={item.id}>
              <button type="button" disabled={item.total_quantity === 0} onClick={() => setProduct(item)}>
                <strong>{item.name}</strong> <small>{item.sku}</small>
                <span className={item.total_quantity === 0 ? "qty qty--low" : "qty"}>{item.total_quantity === 0 ? "Agotado" : `${item.total_quantity} disp.`}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {!product && search && results.data?.length === 0 && !results.loading && <p className="muted">Sin resultados para «{search}».</p>}
      {product && (
        <form className="form-grid form-grid--tight" onSubmit={submit}>
          <p className="field--wide"><strong>{product.name}</strong> <button type="button" className="link" onClick={() => setProduct(null)}>cambiar</button></p>
          <Field label="Tomar de">
            <select className="input" required value={locationId} onChange={(e) => setLocationId(e.target.value)}>
              {product.stock.map((s) => <option key={s.location_id} value={s.location_id}>{s.location_name} ({s.quantity} disp.)</option>)}
            </select>
          </Field>
          <Field label="Cantidad"><input className="input" type="number" min={1} required value={quantity} onChange={(e) => setQuantity(e.target.value)} /></Field>
          <div className="form-actions"><button className="btn btn--primary" disabled={action.busy || !locationId}>Usar repuesto</button></div>
        </form>
      )}
      {action.error && <Notice kind="error">{action.error}</Notice>}
      {action.success && <Notice kind="success">{action.success}</Notice>}
    </div>
  );
}
