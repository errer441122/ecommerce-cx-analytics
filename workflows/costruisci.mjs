// Scrive prima-dell-invio.n8n.json: i nodi Code contengono lo stesso testo di docs/regole.js,
// il nodo AI le stesse istruzioni di ai/istruzioni.txt. I test controllano che restino uguali.
import { readFileSync, writeFileSync } from "node:fs";

const leggi = (f) => readFileSync(new URL(f, import.meta.url), "utf8").replace(/\r\n/g, "\n");
const regole = leggi("../docs/regole.js").replace(/\nif \(typeof module[^\n]*\n?$/, "\n");
const istruzioni = leggi("../ai/istruzioni.txt");

const nodo = (name, type, typeVersion, x, y, parameters, altro = {}) => ({ parameters, id: name.toLowerCase().replace(/[^a-z0-9]+/g, "-"), name, type: `n8n-nodes-base.${type}`, typeVersion, position: [x, y], ...altro });
const valore = (name, value, type = "string") => ({ id: name, name, value, type });

const LEGGI = `// I file diventano testo. Se un file manca, la regola R1 più avanti non fa passare nessuno.
const modulo = $input.first(), testi = {};
for (const campo of ["Destinatari", "Permessi", "Ticket", "Ordini"]) {
  let t = "";
  if (modulo.binary && modulo.binary[campo]) {
    const b = await this.helpers.getBinaryDataBuffer(0, campo);
    t = b.toString("utf8");
    if (t.includes("\\ufffd")) t = b.toString("latin1");   // vecchi file di Excel
  }
  testi[campo.toLowerCase()] = t;
}
return [{ json: { testi, export_del: modulo.json["File scaricati il"], oggi: $now.toFormat("yyyy-MM-dd"), campagna: modulo.json["Campagna"] } }];`;

const REGOLE = `${regole}
// ---------- n8n
const i = $input.first().json, elenco = (s) => String(s).split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);
const passo = regoleFisse(i.testi, i.oggi, i.export_del, {
  domini_interni: elenco(i.domini_interni), fonti_che_riaprono: elenco(i.fonti_che_riaprono),
  giorni_dopo_reclamo: Number(i.giorni_dopo_reclamo), giorni_dopo_consegna: Number(i.giorni_dopo_consegna), giorni_export: Number(i.giorni_export),
});
return [{ json: { ...passo, campagna: i.campagna, oggi: i.oggi } }];`;

const LISTE = `${regole}
// ---------- n8n
const passo = $('Regole fisse (nessuna AI)').first().json;
const risposte = {};
try {
  $('Un ticket alla volta').all().forEach((t, n) => {
    const r = $input.all()[n];
    risposte[t.json.id] = r && r.json.choices ? r.json.choices[0].message.content : null;   // nessuna risposta: decide una persona
  });
} catch (e) { /* nessun testo da leggere */ }
const liste = treListe(passo, risposte), binary = {};
for (const [nome, righe] of Object.entries(liste))
  binary[nome] = await this.helpers.prepareBinaryData(Buffer.from(inCsv(righe, COLONNE_LISTE[nome]), "utf8"), nome + ".csv", "text/csv");
const messaggio = [
  "Campagna: " + (passo.campagna || "senza nome") + " (" + passo.oggi + ")",
  passo.blocchi.length ? "CONTROLLO NON FATTO: " + passo.blocchi.join("; ") : "",
  liste.invia.length + " si possono contattare, " + liste.ferma.length + " fermi, " + liste.controlla.length + " da decidere.",
  ...liste.controlla.map((r) => "- " + r.email + " (" + r.decide + "): " + r.domanda),
  passo.note.length ? "Note sui dati: " + passo.note.join("; ") : "",
].filter(Boolean).join("\\n");
return [{ json: { messaggio, ...Object.fromEntries(Object.entries(liste).map(([k, v]) => [k, v.length])) }, binary }];`;

const CORPO = `={{ JSON.stringify({ model: $('Valori da cambiare').first().json.modello_ai, temperature: 0, max_tokens: 160, reasoning_effort: "none", response_format: { type: "json_object" },
  messages: [{ role: "system", content: ${JSON.stringify(istruzioni)} }, { role: "user", content: 'TESTO DEL TICKET:\\n"""\\n' + $json.testo + '\\n"""' }] }) }}`;

const nodes = [
  nodo("Carica i quattro file", "formTrigger", 2.2, 0, 0, {
    formTitle: "Prima dell'invio", formDescription: "Carica gli export di oggi o di ieri. Non parte nessuna email: ricevi tre liste.",
    formFields: { values: [
      ...["Destinatari", "Permessi", "Ticket", "Ordini"].map((fieldLabel) => ({ fieldLabel, fieldType: "file", multipleFiles: false, acceptFileTypes: ".csv", requiredField: true })),
      { fieldLabel: "File scaricati il", fieldType: "date", requiredField: true }, { fieldLabel: "Campagna", requiredField: true }] }, options: {} }, { webhookId: "prima-dell-invio" }),
  nodo("Leggi i file", "code", 2, 220, 0, { jsCode: LEGGI }),
  nodo("Valori da cambiare", "set", 3.4, 440, 0, { includeOtherFields: true, options: {}, assignments: { assignments: [
    valore("domini_interni", "nostra-azienda.example"), valore("fonti_che_riaprono", "modulo web, doppia conferma, firma in fiera"),
    valore("giorni_dopo_reclamo", 7, "number"), valore("giorni_dopo_consegna", 7, "number"), valore("giorni_export", 1, "number"),
    valore("modello_ai", "qwen3.5:4b"), valore("indirizzo_ai", "http://localhost:11434/v1/chat/completions")] } }),
  nodo("Regole fisse (nessuna AI)", "code", 2, 660, 0, { jsCode: REGOLE }),
  nodo("C'è un testo da leggere?", "if", 2.2, 880, 0, { options: {}, conditions: { combinator: "and", options: { caseSensitive: true, leftValue: "", typeValidation: "strict", version: 2 },
    conditions: [{ id: "c1", leftValue: "={{ $json.daLeggere.length }}", rightValue: 0, operator: { type: "number", operation: "gt" } }] } }),
  nodo("Un ticket alla volta", "splitOut", 1, 1100, -120, { fieldToSplitOut: "daLeggere", options: {} }),
  nodo("AI: è un reclamo?", "httpRequest", 4.2, 1320, -120, { method: "POST", url: "={{ $('Valori da cambiare').first().json.indirizzo_ai }}", sendBody: true, specifyBody: "json", jsonBody: CORPO,
    options: { timeout: 120000, batching: { batch: { batchSize: 1, batchInterval: 0 } } } }, { onError: "continueRegularOutput" }),
  nodo("Tre liste", "code", 2, 1540, 0, { jsCode: LISTE }),
  nodo("Email interna: liste e domande", "emailSend", 2.1, 1760, 0, { fromEmail: "crm@nostra-azienda.example", toEmail: "marketing@nostra-azienda.example",
    subject: "=Prima dell'invio: {{ $json.controlla }} casi da decidere", emailFormat: "text", text: "={{ $json.messaggio }}", options: { attachments: "invia,ferma,controlla" } }),
];
const a = (node) => [{ node, type: "main", index: 0 }];
const connections = {
  "Carica i quattro file": { main: [a("Leggi i file")] }, "Leggi i file": { main: [a("Valori da cambiare")] }, "Valori da cambiare": { main: [a("Regole fisse (nessuna AI)")] },
  "Regole fisse (nessuna AI)": { main: [a("C'è un testo da leggere?")] }, "C'è un testo da leggere?": { main: [a("Un ticket alla volta"), a("Tre liste")] },
  "Un ticket alla volta": { main: [a("AI: è un reclamo?")] }, "AI: è un reclamo?": { main: [a("Tre liste")] }, "Tre liste": { main: [a("Email interna: liste e domande")] },
};
writeFileSync(new URL("prima-dell-invio.n8n.json", import.meta.url), JSON.stringify({ name: "Prima dell'invio: chi si può contattare", nodes, connections, settings: { executionOrder: "v1", timezone: "Europe/Rome" }, pinData: {} }, null, 2) + "\n");
console.log(nodes.length, "nodi");
