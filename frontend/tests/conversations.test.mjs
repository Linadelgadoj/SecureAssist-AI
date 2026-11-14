import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/services/conversations.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(
  source.replace("import.meta.env.VITE_API_BASE_URL", '"http://localhost:8000/api/v1"'),
  { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } },
).outputText;
const api = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

test("conversation requests use the authenticated backend API", async () => {
  const originalFetch = globalThis.fetch;
  let request;
  globalThis.fetch = async (url, init) => {
    request = { url, init };
    return new Response(JSON.stringify({ items: [], next_cursor: null }), { status: 200 });
  };
  try {
    assert.deepEqual(await api.listConversations("user-access-token"), { items: [], next_cursor: null });
    assert.equal(request.url, "http://localhost:8000/api/v1/conversations?limit=20");
    assert.equal(request.init.headers.Authorization, "Bearer user-access-token");
  } finally { globalThis.fetch = originalFetch; }
});

test("new conversations and installer messages use only the supported payload", async () => {
  const originalFetch = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, init) => {
    requests.push({ url, init });
    return new Response(JSON.stringify({ id: "conversation-1" }), { status: 201 });
  };
  try {
    await api.createConversation("token");
    await api.sendMessage("token", "conversation-1", "Sin imagen en monitor");
    assert.equal(requests[0].init.body, "{}");
    assert.deepEqual(JSON.parse(requests[1].init.body), { content_text: "Sin imagen en monitor" });
    assert.match(requests[1].url, /\/conversations\/conversation-1\/messages$/);
  } finally { globalThis.fetch = originalFetch; }
});
