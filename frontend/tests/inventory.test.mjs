import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { afterEach, test } from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/services/inventory.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(
  source.replace("import.meta.env.VITE_API_BASE_URL", '"http://localhost:8000/api/v1"'),
  { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } },
).outputText;
const api = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

function capture(responseBody, status = 200) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return new Response(JSON.stringify(responseBody), { status });
  };
  return calls;
}

test("product search sends only the filters that are set", async () => {
  const calls = capture([]);
  await api.listProducts("tok", { q: "fuente 12v", low_stock: true, category: "" });
  assert.equal(calls[0].url, "http://localhost:8000/api/v1/products?q=fuente+12v&low_stock=true");
  assert.equal(calls[0].init.headers.Authorization, "Bearer tok");
  await api.listProducts("tok", { low_stock: false });
  assert.equal(calls[1].url, "http://localhost:8000/api/v1/products");
});

test("repair parts are posted as JSON to the repair", async () => {
  const calls = capture({ id: "m1" }, 201);
  await api.addRepairPart("tok", "r 1", { product_id: "p", location_id: "l", quantity: 2 });
  assert.equal(calls[0].url, "http://localhost:8000/api/v1/repairs/r%201/parts");
  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(calls[0].init.body), { product_id: "p", location_id: "l", quantity: 2 });
});

test("business conflicts surface the backend message and code", async () => {
  capture({ error: { code: "INSUFFICIENT_STOCK", message: "Existencia insuficiente: hay 1 y se necesitan 2." } }, 409);
  await assert.rejects(
    api.addRepairPart("tok", "r1", { product_id: "p", location_id: "l", quantity: 2 }),
    (error) => error.code === "INSUFFICIENT_STOCK" && error.status === 409 && error.message.includes("hay 1"),
  );
});

test("non-conflict errors use a safe generic message", async () => {
  capture({ error: { code: "FORBIDDEN", message: "Only administrators can perform this action" } }, 403);
  await assert.rejects(api.createProduct("tok", { sku: "x", name: "x", category: "x" }),
    (error) => error.status === 403 && error.message === "Tu rol no permite esta acción.");
});
