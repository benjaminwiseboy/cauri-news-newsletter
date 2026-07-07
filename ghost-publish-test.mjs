// Test de publication d'un article HTML via l'Admin API de Ghost.
// Aucune dépendance externe : JWT via crypto natif, requête via fetch natif (Node 18+).
//
// Usage : node ghost-publish-test.mjs
// Lit GHOST_URL et GHOST_ADMIN_KEY depuis le fichier ghost.env (même dossier).
//
// Par défaut crée un BROUILLON (aucun email envoyé). Pour publier + envoyer,
// changer STATUS en "published" et renseigner NEWSLETTER (slug de la newsletter).

import { readFileSync } from "node:fs";
import { createHmac } from "node:crypto";

const STATUS = "draft";          // "draft" = brouillon sûr | "published" = publie (et envoie si NEWSLETTER défini)
const NEWSLETTER = null;          // ex. "default-newsletter" pour déclencher l'envoi email à la publication

// --- Charger ghost.env ---
function loadEnv(path) {
  const env = {};
  let raw;
  try {
    raw = readFileSync(path, "utf8");
  } catch {
    console.error(`❌ Fichier introuvable : ${path}`);
    console.error("   Crée un fichier ghost.env avec GHOST_URL=... et GHOST_ADMIN_KEY=...");
    process.exit(1);
  }
  for (const line of raw.split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z_]+)\s*=\s*(.*)\s*$/);
    if (m) env[m[1]] = m[2].trim();
  }
  return env;
}

const env = loadEnv(new URL("./ghost.env", import.meta.url));
const GHOST_URL = (env.GHOST_URL || "").replace(/\/+$/, "");
const ADMIN_KEY = env.GHOST_ADMIN_KEY || "";

if (!GHOST_URL || !ADMIN_KEY || !ADMIN_KEY.includes(":")) {
  console.error("❌ GHOST_URL ou GHOST_ADMIN_KEY manquant/invalide dans ghost.env");
  console.error("   GHOST_ADMIN_KEY doit avoir le format identifiant:secret");
  process.exit(1);
}

// --- Construire le JWT Admin API (HS256) ---
function base64url(input) {
  return Buffer.from(input).toString("base64").replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
}

function makeToken(adminKey) {
  const [id, secret] = adminKey.split(":");
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: "HS256", typ: "JWT", kid: id };
  const payload = { iat: now, exp: now + 5 * 60, aud: "/admin/" };
  const data = `${base64url(JSON.stringify(header))}.${base64url(JSON.stringify(payload))}`;
  const sig = createHmac("sha256", Buffer.from(secret, "hex")).update(data).digest("base64")
    .replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
  return `${data}.${sig}`;
}

// --- HTML de test (CSS inline, comme l'exigent Ghost et beehiiv) ---
const html = `
<p style="font-size:16px;line-height:1.6;color:#222;">Bonjour 👋 — ceci est un <strong>article de test</strong> publié automatiquement via l'Admin API de Ghost.</p>
<h2 style="color:#0a3d62;">Test d'intégration BRVM</h2>
<p style="font-size:16px;line-height:1.6;color:#222;">Si tu lis ceci dans ton brouillon Ghost, l'automatisation fonctionne : ton skill pourra publier ses articles HTML sans ressaisie.</p>
<table style="border-collapse:collapse;width:100%;font-size:14px;">
  <tr style="background:#0a3d62;color:#fff;"><th style="padding:8px;text-align:left;">Valeur</th><th style="padding:8px;text-align:right;">Cours</th><th style="padding:8px;text-align:right;">Var.</th></tr>
  <tr><td style="padding:8px;border-bottom:1px solid #eee;">Exemple SA</td><td style="padding:8px;text-align:right;border-bottom:1px solid #eee;">1 250</td><td style="padding:8px;text-align:right;border-bottom:1px solid #eee;color:#1e7e34;">+2,4 %</td></tr>
</table>
`.trim();

const post = {
  posts: [{
    title: `Test API — ${new Date().toLocaleDateString("fr-FR")}`,
    html,
    status: STATUS,
    ...(NEWSLETTER ? { newsletter: NEWSLETTER } : {}),
  }],
};

// --- Appel API ---
const url = `${GHOST_URL}/ghost/api/admin/posts/?source=html`;
console.log(`→ POST ${url}  (status=${STATUS})`);

try {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Ghost ${makeToken(ADMIN_KEY)}`,
      "Content-Type": "application/json",
      "Accept-Version": "v5.0",
    },
    body: JSON.stringify(post),
  });

  const body = await res.json().catch(() => ({}));

  if (!res.ok) {
    console.error(`❌ Échec HTTP ${res.status}`);
    console.error(JSON.stringify(body.errors || body, null, 2));
    process.exit(1);
  }

  const created = body.posts?.[0];
  console.log("✅ Article créé avec succès !");
  console.log(`   Titre  : ${created?.title}`);
  console.log(`   Statut : ${created?.status}`);
  console.log(`   URL    : ${created?.url}`);
  console.log(`   Édition: ${GHOST_URL}/ghost/#/editor/post/${created?.id}`);
} catch (err) {
  console.error("❌ Erreur réseau / exécution :", err.message);
  process.exit(1);
}
