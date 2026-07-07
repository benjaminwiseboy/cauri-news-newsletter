// Teste la publication d'une VRAIE édition du skill dans Ghost.
// 1) lit un fichier HTML complet  2) inline le CSS (juice)  3) extrait le <body>
// 4) publie en BROUILLON via l'Admin API.
//
// Usage : node ghost-publish-real.mjs [fichier.html]
//   défaut : newsletter-brvm-2026-06-26.html

import { readFileSync } from "node:fs";
import { createHmac } from "node:crypto";
import juice from "juice";

const FILE = process.argv[2] || "newsletter-brvm-2026-06-26.html";

// --- env ---
const raw = readFileSync(new URL("./ghost.env", import.meta.url), "utf8");
const env = Object.fromEntries(
  raw.split(/\r?\n/).map((l) => l.match(/^\s*([A-Z_]+)\s*=\s*(.*)\s*$/)).filter(Boolean)
    .map((m) => [m[1], m[2].trim()])
);
const GHOST_URL = (env.GHOST_URL || "").replace(/\/+$/, "");
const ADMIN_KEY = env.GHOST_ADMIN_KEY || "";

// --- JWT ---
const b64 = (s) => Buffer.from(s).toString("base64").replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
function token(k) {
  const [id, secret] = k.split(":");
  const now = Math.floor(Date.now() / 1000);
  const data = `${b64(JSON.stringify({ alg: "HS256", typ: "JWT", kid: id }))}.${b64(JSON.stringify({ iat: now, exp: now + 300, aud: "/admin/" }))}`;
  const sig = createHmac("sha256", Buffer.from(secret, "hex")).update(data).digest("base64").replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
  return `${data}.${sig}`;
}

// --- charge + inline + extrait le corps ---
const fullHtml = readFileSync(new URL(`./${FILE}`, import.meta.url), "utf8");
const inlined = juice(fullHtml);
const bodyMatch = inlined.match(/<body[^>]*>([\s\S]*)<\/body>/i);
let body = bodyMatch ? bodyMatch[1] : inlined;
body = body.replace(/<style[\s\S]*?<\/style>/gi, "").trim(); // Ghost retire <style> de toute façon

console.log(`Fichier : ${FILE}`);
console.log(`Styles inline avant : ${(fullHtml.match(/style="/g) || []).length}  →  après inlining : ${(body.match(/style="/g) || []).length}`);

const post = { posts: [{ title: `Aperçu Ghost — ${FILE}`, html: body, status: "draft" }] };

const res = await fetch(`${GHOST_URL}/ghost/api/admin/posts/?source=html`, {
  method: "POST",
  headers: { Authorization: `Ghost ${token(ADMIN_KEY)}`, "Content-Type": "application/json", "Accept-Version": "v5.0" },
  body: JSON.stringify(post),
});
const out = await res.json().catch(() => ({}));
if (!res.ok) { console.error(`❌ HTTP ${res.status}`, JSON.stringify(out.errors || out, null, 2)); process.exit(1); }
const p = out.posts[0];
console.log("✅ Brouillon créé :");
console.log(`   Édition : ${GHOST_URL}/ghost/#/editor/post/${p.id}`);
