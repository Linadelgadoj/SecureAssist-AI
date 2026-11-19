import { EmptyState, Notice, ROLE_LABEL, useAction, useLoader } from "../components/ui";
import { listUsers, updateUser } from "../services/inventory";
import type { Account, Role } from "../types/inventory";

export function UsersPage({ token, account }: { token: string; account: Account }) {
  const users = useLoader(() => listUsers(token), [token]);
  const action = useAction();

  async function change(user: Account, update: { role?: Role; is_active?: boolean }) {
    if (await action.run(() => updateUser(token, user.id, update), `Se actualizó ${user.email}.`)) void users.reload();
  }

  return (
    <section className="module" aria-labelledby="users-title">
      <header className="module-header">
        <div>
          <span className="workspace-eyebrow">SOLO ADMINISTRADORES</span>
          <h1 id="users-title">Usuarios y roles</h1>
        </div>
      </header>
      <p className="muted">Quien entra por primera vez queda como técnico. Siempre debe quedar al menos un administrador activo.</p>
      {users.error && <Notice kind="error">{users.error}</Notice>}
      {action.error && <Notice kind="error" onClose={() => action.setError(null)}>{action.error}</Notice>}
      {action.success && <Notice kind="success" onClose={() => action.setSuccess(null)}>{action.success}</Notice>}
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Usuario</th><th>Rol</th><th>Estado</th></tr></thead>
          <tbody>
            {users.data?.map((user) => (
              <tr key={user.id}>
                <td><strong>{user.full_name ?? user.email}</strong><small>{user.email}{user.id === account.id ? " · tú" : ""}</small></td>
                <td>
                  <select className="input input--auto" value={user.role} disabled={action.busy}
                    onChange={(e) => void change(user, { role: e.target.value as Role })} aria-label={`Rol de ${user.email}`}>
                    {Object.entries(ROLE_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </td>
                <td>
                  <button className="btn btn--small" type="button" disabled={action.busy}
                    onClick={() => void change(user, { is_active: !user.is_active })}>
                    {user.is_active ? "Activo · desactivar" : "Inactivo · activar"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {users.loading && <EmptyState>Cargando usuarios…</EmptyState>}
      </div>
    </section>
  );
}
