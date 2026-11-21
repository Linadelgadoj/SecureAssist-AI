import { useEffect, useState } from "react";

import { Notice, ROLE_LABEL, useLoader } from "../components/ui";
import { getMe } from "../services/inventory";
import { ClientsPage } from "./ClientsPage";
import { ConversationWorkspace } from "./ConversationWorkspace";
import { InventoryPage } from "./InventoryPage";
import { RepairsPage } from "./RepairsPage";
import { UsersPage } from "./UsersPage";

type Section = "asistente" | "inventario" | "clientes" | "reparaciones" | "usuarios";
const SECTIONS: { id: Section; label: string; adminOnly?: boolean }[] = [
  { id: "asistente", label: "Asistente" },
  { id: "inventario", label: "Inventario" },
  { id: "clientes", label: "Clientes" },
  { id: "reparaciones", label: "Reparaciones" },
  { id: "usuarios", label: "Usuarios", adminOnly: true },
];

/** Lee la sección del hash (#inventario) para que recargar la página no pierda el lugar. */
function sectionFromHash(): Section {
  const value = window.location.hash.replace("#", "") as Section;
  return SECTIONS.some((s) => s.id === value) ? value : "asistente";
}

export function AppShell({ token, onLogout }: { token: string; onLogout: () => void }) {
  const account = useLoader(() => getMe(token), [token]);
  const [section, setSection] = useState<Section>(sectionFromHash);
  const [repairFocus, setRepairFocus] = useState<string | null>(null);

  useEffect(() => {
    const onHash = () => setSection(sectionFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function go(next: Section) {
    window.history.replaceState(null, "", `#${next}`);
    setSection(next);
  }

  if (account.error) {
    return <div className="module"><Notice kind="error">{account.error}</Notice>
      <button className="btn" type="button" onClick={onLogout}>Cerrar sesión</button></div>;
  }
  if (!account.data) return <p className="auth-message module">Cargando tu cuenta…</p>;
  const me = account.data;
  const visible = SECTIONS.filter((s) => !s.adminOnly || me.role === "admin");
  const current = visible.some((s) => s.id === section) ? section : "asistente";

  return (
    <>
      <nav className="app-nav" aria-label="Secciones">
        <div className="app-tabs" role="tablist">
          {visible.map((s) => (
            <button key={s.id} type="button" role="tab" aria-selected={current === s.id}
              className={current === s.id ? "app-tab app-tab--on" : "app-tab"} onClick={() => go(s.id)}>{s.label}</button>
          ))}
        </div>
        <div className="app-user">
          <span><strong>{me.full_name ?? me.email}</strong><small>{ROLE_LABEL[me.role]}</small></span>
          <button className="btn btn--small" type="button" onClick={onLogout}>Salir</button>
        </div>
      </nav>

      {current === "asistente" && <ConversationWorkspace accessToken={token} />}
      {current === "inventario" && <InventoryPage token={token} account={me} />}
      {current === "clientes" && <ClientsPage token={token} onOpenRepair={(id) => { setRepairFocus(id); go("reparaciones"); }} />}
      {current === "reparaciones" && <RepairsPage token={token} account={me} focusId={repairFocus} onFocus={setRepairFocus} />}
      {current === "usuarios" && <UsersPage token={token} account={me} />}
    </>
  );
}
