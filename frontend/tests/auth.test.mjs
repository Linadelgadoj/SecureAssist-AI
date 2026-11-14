import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { afterEach, test } from "node:test";
import ts from "typescript";

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;
const authSource = await readFile(new URL("../src/services/auth.ts", import.meta.url), "utf8");
const authJavaScript = ts.transpileModule(
  authSource.replace("import.meta.env.VITE_API_BASE_URL", '"http://localhost:8000/api/v1"'),
  { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } },
).outputText;
const auth = await import(`data:text/javascript;base64,${Buffer.from(authJavaScript).toString("base64")}`);

afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.window = originalWindow;
});

test("session requests include cookies and parse the real backend response", async () => {
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url, options };
    return new Response(JSON.stringify({ authenticated: false, user: null, access_token: null }), { status: 200 });
  };
  const result = await auth.getSession();
  assert.equal(request.url, "http://localhost:8000/api/v1/auth/session");
  assert.equal(request.options.credentials, "include");
  assert.equal(result.authenticated, false);
});

test("Google sign-in navigates to the backend facade", () => {
  let target;
  globalThis.window = { location: { assign: (url) => { target = url; } } };
  auth.beginGoogleSignIn();
  assert.equal(target, "http://localhost:8000/api/v1/auth/google/start");
});

test("concurrent initial session checks share one network request", async () => {
  let calls = 0;
  let complete;
  globalThis.fetch = () => {
    calls += 1;
    return new Promise((resolve) => { complete = resolve; });
  };
  const first = auth.getSession();
  const second = auth.getSession();
  assert.equal(calls, 1);
  complete(new Response(JSON.stringify({ authenticated: false, user: null, access_token: null }), { status: 200 }));
  await Promise.all([first, second]);
});

test("refresh failure is reported without persisting or logging tokens", async () => {
  globalThis.fetch = async () => new Response("{}", { status: 401 });
  await assert.rejects(auth.refreshSession(), { name: "AuthApiError", status: 401 });
  const context = await readFile(new URL("../src/context/AuthContext.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(context, /localStorage|sessionStorage|indexedDB|console\.(log|info|debug)/i);
});

test("no Supabase or provider credentials are exposed in frontend source", async () => {
  const files = [
    "../src/services/auth.ts", "../src/context/AuthContext.tsx", "../src/App.tsx",
  ];
  for (const file of files) {
    const source = await readFile(new URL(file, import.meta.url), "utf8");
    assert.doesNotMatch(source, /SUPABASE_PUBLISHABLE_KEY|service_role|client_secret|OPENAI_API_KEY/i);
  }
});
