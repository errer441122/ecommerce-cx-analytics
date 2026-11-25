// Fa leggere i testi di prova a un modello vero e scrive cosa succede a ogni cliente.
//   node ai/prova.mjs                        (Ollama sul proprio PC, qwen3.5:4b)
//   AI_URL=... AI_MODELLO=... AI_CHIAVE=... node ai/prova.mjs   (qualunque servizio compatibile con OpenAI)
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const qui = new URL("..", import.meta.url);
const leggi = (f) => readFileSync(new URL(f, qui), "utf8");
const { regolaAI, regoleFisse, VALORI } = createRequire(import.meta.url)("../docs/regole.js");
const URL_AI = process.env.AI_URL || "http://127.0.0.1:11434/v1/chat/completions", MODELLO = process.env.AI_MODELLO || "qwen3.5:4b";

async function chiedi(testo) {
  const corpo = { model: MODELLO, temperature: 0, max_tokens: 160, reasoning_effort: "none", response_format: { type: "json_object" },
    messages: [{ role: "system", content: leggi("ai/istruzioni.txt") }, { role: "user", content: `TESTO DEL TICKET:\n"""\n${testo}\n"""` }] };
  const r = await fetch(URL_AI, { method: "POST", headers: { "Content-Type": "application/json", ...(process.env.AI_CHIAVE ? { Authorization: `Bearer ${process.env.AI_CHIAVE}` } : {}) }, body: JSON.stringify(corpo) });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return (await r.json()).choices[0].message.content;
}

const risultati = [];
for (const c of JSON.parse(leggi("ai/casi.json"))) {
  const risposta = await chiedi(c.testo), esito = regolaAI(c, risposta, VALORI);
  let letto = ""; try { letto = JSON.parse(risposta).tipo; } catch {}
  risultati.push({ ...c, risposta, letto, esito: esito.ferma ? "ferma" : "decide una persona" });
  console.log(c.id, c.atteso, "->", letto, "->", risultati.at(-1).esito);
}
const reclami = risultati.filter((r) => r.atteso === "reclamo"), conta = (f) => risultati.filter(f).length;
const riepilogo = { modello: MODELLO, data: new Date().toISOString().slice(0, 10), testi: risultati.length,
  reclami: reclami.length, reclami_fermati_subito: reclami.filter((r) => r.esito === "ferma").length,
  domande: conta((r) => r.atteso === "domanda"), domande_proposte_giuste: conta((r) => r.atteso === "domanda" && ["domanda", "richiesta_commerciale"].includes(r.letto)),
  fermati_per_errore: conta((r) => r.atteso !== "reclamo" && r.esito === "ferma"),
  passati_senza_una_persona: 0, // per costruzione: regolaAI non restituisce mai "invia" (vedi i test)
  sarebbero_passati_se_l_ai_potesse_decidere: conta((r) => r.atteso !== "domanda" && ["domanda", "richiesta_commerciale"].includes(r.letto)) };
writeFileSync(new URL("ai/risultati.json", qui), JSON.stringify({ riepilogo, risultati }, null, 1) + "\n");

const testi = Object.fromEntries(["destinatari", "permessi", "ticket", "ordini"].map((n) => [n, leggi(`docs/esempio/${n}.csv`)]));
const esempio = {};
for (const t of regoleFisse(testi, "2026-11-25", "2026-11-25").daLeggere) if (t.id !== "T-110") esempio[t.id] = await chiedi(t.testo); // T-110: l'AI che non risponde
writeFileSync(new URL("docs/esempio/risposte-ai.json", qui), JSON.stringify(esempio, null, 1) + "\n");
console.log(riepilogo);
