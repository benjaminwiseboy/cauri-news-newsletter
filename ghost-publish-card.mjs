// Publie une édition en préservant le HTML VERBATIM via une "HTML card" Lexical.
// Contrairement à ?source=html (qui convertit en blocs natifs et jette les styles),
// la carte HTML garde les styles inline, les <div> décorés, les fonds de couleur.
//
// Usage : node ghost-publish-card.mjs [fichier.html]

import { readFileSync } from "node:fs";
import { createHmac } from "node:crypto";
import juice from "juice";

const FILE = process.argv[2] || "newsletter-brvm-2026-06-26.html";

const raw = readFileSync(new URL("./ghost.env", import.meta.url), "utf8");
const env = Object.fromEntries(
  raw.split(/\r?\n/).map((l) => l.match(/^\s*([A-Z_]+)\s*=\s*(.*)\s*$/)).filter(Boolean).map((m) => [m[1], m[2].trim()])
);
const GHOST_URL = (env.GHOST_URL || "").replace(/\/+$/, "");
const ADMIN_KEY = env.GHOST_ADMIN_KEY || "";

const b64 = (s) => Buffer.from(s).toString("base64").replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
function token(k) {
  const [id, secret] = k.split(":");
  const now = Math.floor(Date.now() / 1000);
  const data = `${b64(JSON.stringify({ alg: "HS256", typ: "JWT", kid: id }))}.${b64(JSON.stringify({ iat: now, exp: now + 300, aud: "/admin/" }))}`;
  const sig = createHmac("sha256", Buffer.from(secret, "hex")).update(data).digest("base64").replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
  return `${data}.${sig}`;
}

// inline le CSS puis extrait le corps
const fullHtml = readFileSync(new URL(`./${FILE}`, import.meta.url), "utf8");
const inlined = juice(fullHtml);
let body = (inlined.match(/<body[^>]*>([\s\S]*)<\/body>/i)?.[1] ?? inlined).replace(/<style[\s\S]*?<\/style>/gi, "").trim();

// Document Lexical : une seule carte HTML contenant le corps verbatim
const lexical = JSON.stringify({
  root: {
    type: "root", format: "", indent: 0, version: 1, direction: null,
    children: [{ type: "html", version: 1, html: body }],
  },
});

const post = { posts: [{ title: `Carte HTML — ${FILE}`, lexical, status: "draft" }] };

const res = await fetch(`${GHOST_URL}/ghost/api/admin/posts/`, {
  method: "POST",
  headers: { Authorization: `Ghost ${token(ADMIN_KEY)}`, "Content-Type": "application/json", "Accept-Version": "v5.0" },
  body: JSON.stringify(post),
});
const out = await res.json().catch(() => ({}));
if (!res.ok) { console.error(`❌ HTTP ${res.status}`, JSON.stringify(out.errors || out, null, 2)); process.exit(1); }
const p = out.posts[0];
console.log("✅ Brouillon (carte HTML) créé :");
console.log(`   Édition : ${GHOST_URL}/ghost/#/editor/post/${p.id}`);
