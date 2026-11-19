import { useState } from "react";
import type { FormEvent } from "react";

import {
  EQUIPMENT_STATUS_LABEL, EmptyState, Field, Notice, REPAIR_STATUS_LABEL, StatusBadge, formatDate, optional,
  useAction, useLoader,
} from "../components/ui";
import { addEquipment, createClient, getClient, getEquipment, listClients, openRepair } from "../services/inventory";
import type { ClientDetail, Equipment } from "../types/inventory";

interface Props { token: string; onOpenRepair: (repairId: string) => void }

export function ClientsPage({ token, onOpenRepair }: Props) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const clients = useLoader(() => listClients(token, search), [token, search]);

  return (
    <section className="module" aria-labelledby="clients-title">
      <header className="module-header">
        <div>
          <span className="workspace-eyebrow">CLIENTES Y EQUIPOS INSTALADOS</span>
          <h1 id="clients-title">Clientes</h1>
        </div>
        <div className="module-actions">
          <button className="btn btn--primary" type="button" onClick={() => setCreating(!creating)}>＋ Nuevo cliente</button>
        </div>
      </header>

      {creating && <ClientForm token={token} onDone={(client) => {
        setCreating(false); setSelectedId(client.id); void clients.reload();
      }} />}

      <form className="toolbar" role="search" onSubmit={(e) => { e.preventDefault(); setSearch(query.trim()); }}>
        <input className="input" type="search" placeholder="Buscar por nombre, documento, teléfono o dirección…" value={query}
          onChange={(e) => setQuery(e.target.value)} aria-label="Buscar clientes" maxLength={100} />
        <button className="btn" type="submit">Buscar</button>
      </form>
      {clients.error && <Notice kind="error">{clients.error}</Notice>}

      <div className="split">
        <div className="list">
          {clients.data?.map((client) => (
            <button key={client.id} type="button" className={`list-item${client.id === selectedId ? " list-item--active" : ""}`}
              onClick={() => setSelectedId(client.id)}>
              <strong>{client.name}</strong>
              <small>{[client.phone, client.address].filter(Boolean).join(" · ") || "Sin datos de contacto"}</small>
              <span className="list-meta">{client.equipment_count} equipos{client.open_repairs > 0 && <b> · {client.open_repairs} reparación(es) abiertas</b>}</span>
            </button>
          ))}
          {clients.loading && <EmptyState>Cargando clientes…</EmptyState>}
          {!clients.loading && clients.data?.length === 0 && <EmptyState>No hay clientes que coincidan.</EmptyState>}
        </div>
        <aside className="detail">
          {selectedId
            ? <ClientPanel key={selectedId} token={token} clientId={selectedId} onOpenRepair={onOpenRepair}
                onChanged={() => void clients.reload()} />
            : <EmptyState>Selecciona un cliente para ver sus equipos.</EmptyState>}
        </aside>
      </div>
    </section>
  );
}

function ClientForm({ token, onDone }: { token: string; onDone: (client: ClientDetail) => void }) {
  const action = useAction();
  const [form, setForm] = useState({ name: "", document_id: "", phone: "", email: "", address: "", notes: "" });
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  async function submit(event: FormEvent) {
    event.preventDefault();
    const result: { client: ClientDetail | null } = { client: null };
    const ok = await action.run(async () => {
      result.client = await createClient(token, {
        name: form.name.trim(), document_id: optional(form.document_id), phone: optional(form.phone),
        email: optional(form.email), address: optional(form.address), notes: optional(form.notes),
      });
    });
    if (ok && result.client) onDone(result.client);
  }

  return (
    <form className="card form-grid" onSubmit={submit}>
      <h2 className="card-title">Nuevo cliente</h2>
      <Field label="Nombre o razón social"><input className="input" required maxLength={200} value={form.name} onChange={set("name")} /></Field>
      <Field label="Documento / NIT"><input className="input" maxLength={30} value={form.document_id} onChange={set("document_id")} /></Field>
      <Field label="Teléfono"><input className="input" maxLength={30} value={form.phone} onChange={set("phone")} /></Field>
      <Field label="Correo"><input className="input" type="email" maxLength={320} value={form.email} onChange={set("email")} /></Field>
      <Field label="Dirección" wide><input className="input" maxLength={300} value={form.address} onChange={set("address")} /></Field>
      <Field label="Notas" wide><input className="input" maxLength={2000} value={form.notes} onChange={set("notes")} /></Field>
      {action.error && <Notice kind="error">{action.error}</Notice>}
      <div className="form-actions"><button className="btn btn--primary" disabled={action.busy}>{action.busy ? "Guardando…" : "Crear cliente"}</button></div>
    </form>
  );
}

function ClientPanel({ token, clientId, onOpenRepair, onChanged }: {
  token: string; clientId: string; onOpenRepair: (id: string) => void; onChanged: () => void;
}) {
  const client = useLoader(() => getClient(token, clientId), [token, clientId]);
  const [addingEquipment, setAddingEquipment] = useState(false);
  const [equipmentId, setEquipmentId] = useState<string | null>(null);

  if (client.loading && !client.data) return <EmptyState>Cargando…</EmptyState>;
  if (client.error || !client.data) return <Notice kind="error">{client.error ?? "No se encontró el cliente."}</Notice>;
  const data = client.data;

  return (
    <div className="detail-body">
      <span className="workspace-eyebrow">CLIENTE</span>
      <h2 className="detail-title">{data.name}</h2>
      <p className="muted">{[data.document_id, data.phone, data.email].filter(Boolean).join(" · ") || "Sin datos de contacto"}</p>
      {data.address && <p>{data.address}</p>}
      {data.notes && <p className="muted">{data.notes}</p>}

      <div className="section-head">
        <h3 className="section-title">Equipos instalados</h3>
        <button className="btn btn--small" type="button" onClick={() => setAddingEquipment(!addingEquipment)}>＋ Equipo</button>
      </div>
      {addingEquipment && <EquipmentForm token={token} clientId={clientId} onDone={() => {
        setAddingEquipment(false); void client.reload(); onChanged();
      }} />}
      <ul className="equipment-list">
        {data.equipment.length === 0 && <li className="muted">Este cliente no tiene equipos registrados.</li>}
        {data.equipment.map((item) => (
          <li key={item.id}>
            <button type="button" className={`equipment-item${equipmentId === item.id ? " equipment-item--active" : ""}`}
              onClick={() => setEquipmentId(equipmentId === item.id ? null : item.id)}>
              <span><strong>{equipmentLabel(item)}</strong>
                <small>{[item.serial_number && `S/N ${item.serial_number}`, item.site_description].filter(Boolean).join(" · ") || "Sin serial ni ubicación"}</small></span>
              <StatusBadge status={item.status} label={EQUIPMENT_STATUS_LABEL[item.status]} />
            </button>
            {equipmentId === item.id && (
              <EquipmentHistory token={token} clientId={clientId} equipmentId={item.id} onOpenRepair={onOpenRepair}
                onChanged={() => { void client.reload(); onChanged(); }} />
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function equipmentLabel(item: Pick<Equipment, "equipment_type" | "brand" | "model">): string {
  return [item.equipment_type, item.brand, item.model].filter(Boolean).join(" ");
}

function EquipmentForm({ token, clientId, onDone }: { token: string; clientId: string; onDone: () => void }) {
  const action = useAction();
  const [form, setForm] = useState({ equipment_type: "", brand: "", model: "", serial_number: "", site_description: "", installed_on: "" });
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  async function submit(event: FormEvent) {
    event.preventDefault();
    const ok = await action.run(() => addEquipment(token, clientId, {
      equipment_type: form.equipment_type.trim(), brand: optional(form.brand), model: optional(form.model),
      serial_number: optional(form.serial_number), site_description: optional(form.site_description),
      installed_on: optional(form.installed_on),
    }));
    if (ok) onDone();
  }

  return (
    <form className="card card--compact form-grid form-grid--tight" onSubmit={submit}>
      <Field label="Tipo de equipo"><input className="input" required maxLength={60} list="equipment-types" placeholder="Cámara domo, DVR…" value={form.equipment_type} onChange={set("equipment_type")} /></Field>
      <datalist id="equipment-types">{["Cámara bala", "Cámara domo", "Cámara PTZ", "DVR", "NVR", "Fuente", "Switch PoE", "Disco duro"].map((t) => <option key={t} value={t} />)}</datalist>
      <Field label="Marca"><input className="input" maxLength={100} value={form.brand} onChange={set("brand")} /></Field>
      <Field label="Modelo"><input className="input" maxLength={100} value={form.model} onChange={set("model")} /></Field>
      <Field label="Número de serie"><input className="input" maxLength={100} value={form.serial_number} onChange={set("serial_number")} /></Field>
      <Field label="Ubicación en el sitio"><input className="input" maxLength={300} placeholder="Entrada, bodega, piso 2…" value={form.site_description} onChange={set("site_description")} /></Field>
      <Field label="Instalado el"><input className="input" type="date" value={form.installed_on} onChange={set("installed_on")} /></Field>
      {action.error && <Notice kind="error">{action.error}</Notice>}
      <div className="form-actions"><button className="btn btn--primary" disabled={action.busy}>{action.busy ? "Guardando…" : "Agregar equipo"}</button></div>
    </form>
  );
}

function EquipmentHistory({ token, clientId, equipmentId, onOpenRepair, onChanged }: {
  token: string; clientId: string; equipmentId: string; onOpenRepair: (id: string) => void; onChanged: () => void;
}) {
  const equipment = useLoader(() => getEquipment(token, equipmentId), [token, equipmentId]);
  const action = useAction();
  const [problem, setProblem] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    let repairId = "";
    const ok = await action.run(async () => {
      repairId = (await openRepair(token, { client_id: clientId, equipment_id: equipmentId, problem_description: problem.trim() })).id;
    });
    if (ok) { onChanged(); onOpenRepair(repairId); }
  }

  return (
    <div className="equipment-history">
      {equipment.error && <Notice kind="error">{equipment.error}</Notice>}
      <h4>Historial de reparaciones</h4>
      <ul className="timeline">
        {equipment.data?.repairs.length === 0 && <li className="muted">Sin reparaciones registradas.</li>}
        {equipment.data?.repairs.map((repair) => (
          <li key={repair.id}>
            <StatusBadge status={repair.status} label={REPAIR_STATUS_LABEL[repair.status]} />
            <div>
              <button type="button" className="link" onClick={() => onOpenRepair(repair.id)}>{repair.problem_description}</button>
              <small>{formatDate(repair.opened_at)} · {repair.technician_name ?? repair.technician_email}
                {repair.solution ? ` · ${repair.solution}` : ""}{repair.parts_count ? ` · ${repair.parts_count} repuesto(s)` : ""}</small>
            </div>
          </li>
        ))}
      </ul>
      <form className="inline-form" onSubmit={submit}>
        <input className="input" required maxLength={4000} placeholder="Describe la falla para abrir una reparación…" value={problem}
          onChange={(e) => setProblem(e.target.value)} aria-label="Problema reportado" />
        <button className="btn btn--primary" disabled={action.busy}>Abrir reparación</button>
      </form>
      {action.error && <Notice kind="error">{action.error}</Notice>}
    </div>
  );
}
