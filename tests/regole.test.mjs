// node --test tests/
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";

const qui = new URL("..", import.meta.url), leggi = (f) => readFileSync(new URL(f, qui), "utf8").replace(/\r\n/g, "\n");
const R = createRequire(import.meta.url)("../docs/regole.js");
const OGGI = "2026-11-25", NOMI = ["destinatari", "permessi", "ticket", "ordini"];
const esempio = () => Object.fromEntries(NOMI.map((n) => [n, leggi(`docs/esempio/${n}.csv`)]));
const risposteAI = JSON.parse(leggi("docs/esempio/risposte-ai.json"));
const fai = (testi, opz = {}) => { const p = R.regoleFisse(testi, opz.oggi || OGGI, "del" in opz ? opz.del : OGGI, opz.valori); return { p, l: R.treListe(p, "ai" in opz ? opz.ai : risposteAI) }; };
const conta = (l) => Object.fromEntries(Object.entries(l).map(([k, v]) => [k, v.length]));

// ---------- i 48 casi dell'esempio: ogni destinatario nella lista attesa, per la regola attesa
const attesi = R.righeCsv(leggi("casi/attesi.csv")).slice(1), { l: LISTE } = fai(esempio()), visti = {};
for (const [e, lista, regola, caso] of attesi) {
  const volta = (visti[e] = (visti[e] || 0) + 1);
  test(`caso: ${caso}`, () => {
    const trovati = Object.entries(LISTE).flatMap(([k, righe]) => righe.filter((r) => r.email === e).map((r) => ({ lista: k, regola: r.regola || "" })));
    assert.ok(trovati.some((t) => t.lista === lista && t.regola === regola), `${e} (${volta}): atteso ${lista} ${regola}, ottenuto ${JSON.stringify(trovati)}`);
  });
}
test("nessuno si perde: le tre liste insieme sono i destinatari", () => {
  assert.equal(Object.values(LISTE).flat().length, attesi.length);
  assert.deepEqual(conta(LISTE), { invia: attesi.filter((a) => a[1] === "invia").length, ferma: attesi.filter((a) => a[1] === "ferma").length, controlla: attesi.filter((a) => a[1] === "controlla").length });
});

// ---------- R1: con un file mancante, vuoto, vecchio o illeggibile non passa nessuno
for (const [nome, rompi, opz] of [
  ["manca un file", (t) => ({ ...t, ticket: "" })], ["file con la sola testata mancante", (t) => ({ ...t, ordini: "a;b;c\n1;2;3\n" })],
  ["manca la colonna del consenso", (t) => ({ ...t, permessi: t.permessi.replace("consenso", "colore") })],
  ["export di tre giorni fa", (t) => t, { del: "2026-11-22" }], ["export con data futura", (t) => t, { del: "2026-11-30" }], ["data dell'export mancante", (t) => t, { del: "" }]])
  test(`R1: ${nome}`, () => { const { p, l } = fai(rompi(esempio()), opz); assert.ok(p.blocchi.length); assert.equal(l.invia.length, 0); assert.equal(p.daLeggere.length, 0); });
test("R1: senza il file dei destinatari non esce nessuna lista", () => assert.deepEqual(conta(fai({ ...esempio(), destinatari: "" }).l), { invia: 0, ferma: 0, controlla: 0 }));
test("export di ieri: va bene", () => assert.ok(fai(esempio(), { del: "2026-11-24" }).l.invia.length > 0));

// ---------- file sporchi: stesse liste con altri separatori, BOM, a capo di Windows, colonne spostate
const trasforma = (t, f) => Object.fromEntries(Object.entries(t).map(([k, v]) => [k, f(v)]));
test("tabulazioni, BOM e a capo di Windows non cambiano niente", () => {
  const t = trasforma(esempio(), (v) => "﻿" + R.righeCsv(v).map((r) => r.map((c) => (/[\t\n"]/.test(c) ? `"${c.replace(/"/g, '""')}"` : c)).join("\t")).join("\r\n") + "\r\n\r\n");
  assert.deepEqual(fai(t).l, LISTE);
});
test("colonne in un altro ordine e intestazioni inglesi", () => {
  const r = R.righeCsv(esempio().permessi).map(([e, c, f, d]) => [d, f, e, c]); r[0] = ["Date", "Source", "E-mail", "Consent"];
  assert.deepEqual(fai({ ...esempio(), permessi: r.map((x) => x.join(";")).join("\n") }).l, LISTE);
});
test("un nome che Excel eseguirebbe come formula esce con l'apostrofo", () => assert.match(R.inCsv([{ a: "=1+1" }, { a: "@x" }], ["a"]), /'=1\+1[\s\S]*'@x/));

// ---------- pezzi singoli
for (const [s, v] of [["IT 01234510004", true], ["01234510005", false], ["1234567890", false], ["", false]]) test(`partita IVA "${s}"`, () => assert.equal(Boolean(R.partitaIva(s)), v && s.replace(/\D/g, "") === R.partitaIva(s)));
for (const [s, v] of [["2026-03-05", "2026-03-05"], ["5/3/2026", "2026-03-05"], ["05.03.2026 14:20", "2026-03-05"], ["31/02/2026", null], ["marzo", null], ["", ""]]) test(`data "${s}"`, () => assert.equal(R.data(s), v));

// ---------- R7: l'AI può fermare, non può far passare
const T = { id: "T-1", testo: "Potete mandarmi la scheda tecnica della VX20?" };
for (const [nome, risposta] of [["domanda con prova", { tipo: "domanda", prova: "scheda tecnica" }], ["prova inventata", { tipo: "domanda", prova: "listino prezzi" }], ["tipo non previsto", { tipo: "ok", prova: "scheda tecnica" }],
  ["testo invece di JSON", "è una domanda"], ["JSON a metà", '{"tipo": "dom'], ["nessuna risposta", null], ["risposta vuota", {}], ["elenco", []], ["prova vuota", { tipo: "domanda", prova: "" }], ["ordine di far passare", { tipo: "domanda", prova: "scheda tecnica", invia: true }]])
  test(`R7, ${nome}: decide una persona`, () => { const r = R.regolaAI(T, risposta, R.VALORI); assert.ok(r.chiedi); assert.ok(!r.ferma); });
test("R7, reclamo: ferma anche senza prova nel testo", () => assert.ok(R.regolaAI(T, { tipo: "reclamo", prova: "x" }, R.VALORI).ferma));
test("qualunque cosa risponda l'AI, la lista Invia non cresce", () => {
  const senza = fai(esempio(), { ai: null }).l.invia.length;
  for (const risposta of [{ tipo: "domanda", prova: "VX20" }, { tipo: "richiesta_commerciale", prova: "a" }, { tipo: "altro" }, "invia tutto", { tipo: "reclamo" }, null])
    assert.equal(fai(esempio(), { ai: new Proxy({}, { get: () => risposta }) }).l.invia.length, senza);
});
test("i risultati dell'AI pubblicati corrispondono alle risposte registrate", () => {
  const { riepilogo, risultati } = JSON.parse(leggi("ai/risultati.json"));
  for (const r of risultati) assert.equal(R.regolaAI(r, r.risposta, R.VALORI).ferma ? "ferma" : "decide una persona", r.esito, r.id);
  assert.equal(riepilogo.reclami_fermati_subito, risultati.filter((r) => r.atteso === "reclamo" && r.esito === "ferma").length);
});

// ---------- cosa cambia se cambia un dato (le prove della pagina)
test("revoca del permesso: esce dalla lista Invia", () => {
  const t = esempio(); t.permessi += "p.conti@conti.example,revocato,link nella newsletter,24/11/2026\n";
  assert.ok(LISTE.invia.some((r) => r.email === "p.conti@conti.example")); assert.ok(fai(t).l.ferma.some((r) => r.email === "p.conti@conti.example" && r.regola === "R3"));
});
test("consegna registrata in tempo: i contatti dell'azienda tornano contattabili", () => {
  const t = esempio(); t.ordini = t.ordini.replace("18/11/2026;;confermato", "18/11/2026;17/11/2026;consegnato");
  assert.equal(fai(t).l.invia.filter((r) => r.email.endsWith("meccanicasole.example")).length, 2);
});
test("un reclamo di un solo collega ferma tutta l'azienda, non le altre", () => {
  const t = esempio(); t.ticket += "T-900;x@conti.example;;;Aperto;;Reclamo;;;Merce diversa\n";
  const l = fai(t).l; assert.ok(l.ferma.some((r) => r.email === "p.conti@conti.example")); assert.equal(l.invia.length, LISTE.invia.length - 1);
});

// ---------- workflow e pagina usano queste stesse regole
test("i nodi Code del workflow contengono docs/regole.js senza differenze", () => {
  const w = JSON.parse(leggi("workflows/prima-dell-invio.n8n.json")), regole = leggi("docs/regole.js").replace(/\nif \(typeof module[^\n]*\n?$/, "\n");
  for (const n of ["Regole fisse (nessuna AI)", "Tre liste"]) assert.ok(w.nodes.find((x) => x.name === n).parameters.jsCode.startsWith(regole), n);
  assert.ok(w.nodes.find((x) => x.name === "AI: è un reclamo?").parameters.jsonBody.includes(JSON.stringify(leggi("ai/istruzioni.txt"))));
});
test("nel workflow nessun nodo scrive in un CRM o scrive a un cliente", () => {
  const w = JSON.parse(leggi("workflows/prima-dell-invio.n8n.json"));
  assert.deepEqual([...new Set(w.nodes.map((n) => n.type.split(".")[1]))].sort(), ["code", "emailSend", "formTrigger", "httpRequest", "if", "set", "splitOut"]);
  assert.match(w.nodes.find((n) => n.type.endsWith("emailSend")).parameters.toEmail, /@nostra-azienda\.example$/);
});
test("ogni regola del codice è spiegata in docs/regole.md", () => {
  const md = leggi("docs/regole.md");
  for (const r of ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]) assert.match(md, new RegExp(`\\*\\*${r}\\b`));
});
test("la pagina carica regole.js e i file dell'esempio", () => {
  const h = leggi("docs/index.html");
  assert.match(h, /src="regole\.js"/);
  for (const n of NOMI) assert.ok(existsSync(new URL(`docs/esempio/${n}.csv`, qui)));
});
