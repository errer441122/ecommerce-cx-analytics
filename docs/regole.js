// Prima dell'invio: chi si può contattare, chi va fermato, cosa deve decidere una persona.
// Queste funzioni girano uguali nella pagina, nei test e nei nodi Code di n8n. Nessuna libreria.
// Le parole e i numeri da cambiare sono in VALORI. Le regole, a parole: docs/regole.md.

const VALORI = {
  giorni_dopo_reclamo: 7,
  giorni_dopo_consegna: 7,
  giorni_export: 1,
  domini_interni: ["nostra-azienda.example"],
  domini_personali: ["gmail.com", "libero.it", "outlook.com", "outlook.it", "hotmail.com", "hotmail.it", "yahoo.com", "yahoo.it",
    "icloud.com", "live.it", "virgilio.it", "tiscali.it", "alice.it", "pec.it", "legalmail.it"],
  dice_si: ["si", "yes", "true", "1", "confermato", "iscritto", "opt-in"],
  dice_no: ["no", "false", "0", "negato", "revocato", "disiscritto", "unsubscribed", "opt-out"],
  fonti_che_riaprono: ["modulo web", "doppia conferma", "firma in fiera"],
  ticket_chiuso: ["chiuso", "risolto", "closed", "solved"],
  categorie_che_fermano: ["reclamo", "garanzia", "reso", "danno", "ritardo"],
  categorie_innocue: ["richiesta catalogo", "informazioni prodotto", "copia fattura"],
  priorita_che_fermano: ["alta", "urgente", "high", "urgent"],
  ordini_che_non_contano: ["annullato", "cancelled", "reso", "nota di credito"],
  inizio_parole_allarme: ["reclam", "rott", "dannegg", "difett", "guast", "rimbors", "avvocat", "legale", "legali", "disdett", "disdir",
    "contestaz", "sbagliat", "inaccettabil", "delus", "penal", "complain", "refund", "broken", "damaged"],
};

// ---------- leggere i file come escono davvero dai programmi

const COLONNE = {
  destinatari: { email: ["email", "e_mail", "indirizzo_email", "mail"], nome: ["nome", "name", "contatto"], azienda: ["azienda", "company", "ragione_sociale"],
    piva: ["partita_iva", "p_iva", "piva", "vat"], responsabile: ["responsabile", "owner", "proprietario"] },
  permessi: { email: ["email", "e_mail", "mail"], permesso: ["permesso", "consenso", "consent", "stato"], fonte: ["fonte", "source", "origine"], data: ["data", "date", "data_consenso"] },
  ticket: { id: ["id", "ticket", "numero"], email: ["email", "e_mail", "mail", "richiedente"], azienda: ["azienda", "company", "ragione_sociale"], piva: ["partita_iva", "p_iva", "piva", "vat"],
    stato: ["stato", "status"], priorita: ["priorita", "priority"], categoria: ["categoria", "category", "tipo"], chiuso: ["chiuso_il", "closed_at", "data_chiusura"], testo: ["testo", "descrizione", "description", "oggetto"] },
  ordini: { numero: ["numero", "ordine", "order"], azienda: ["azienda", "cliente", "company", "ragione_sociale"], piva: ["partita_iva", "p_iva", "piva", "vat"], email: ["email", "e_mail", "mail"],
    promessa: ["data_promessa", "consegna_promessa", "promised_date"], consegna: ["data_consegna", "consegnato_il", "delivered_date"], stato: ["stato", "status"] },
};
const OBBLIGATORIE = { destinatari: ["email"], permessi: ["email", "permesso", "fonte", "data"], ticket: ["id", "stato", "testo"], ordini: ["numero", "promessa", "consegna"] };

const senzaAccenti = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "");
const parola = (s) => senzaAccenti(String(s ?? "")).replace(/ /g, " ").trim().toLowerCase().replace(/\s+/g, " ");
const chiaveColonna = (s) => parola(s).replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");

function righeCsv(testo) {
  const t = String(testo ?? "").replace(/^﻿/, "");
  const prima = t.split("\n", 1)[0];
  const sep = [";", ",", "\t"].sort((a, b) => prima.split(b).length - prima.split(a).length)[0];
  const righe = []; let riga = [], campo = "", dentro = false;
  for (let i = 0; i < t.length; i++) {
    const c = t[i];
    if (dentro) { if (c === '"') { if (t[i + 1] === '"') { campo += '"'; i++; } else dentro = false; } else campo += c; }
    else if (c === '"' && campo === "") dentro = true;
    else if (c === sep) { riga.push(campo); campo = ""; }
    else if (c === "\n" || c === "\r") { if (c === "\r" && t[i + 1] === "\n") i++; riga.push(campo); campo = ""; righe.push(riga); riga = []; }
    else campo += c;
  }
  if (campo !== "" || riga.length) { riga.push(campo); righe.push(riga); }
  return righe.filter((r) => r.some((x) => x.trim() !== ""));
}

function leggi(nome, testo) {
  const righe = righeCsv(testo);
  if (!righe.length) return { errore: `${nome}: il file è vuoto o manca` };
  const testata = righe[0].map(chiaveColonna), posto = {};
  for (const [campo, nomi] of Object.entries(COLONNE[nome])) { const i = testata.findIndex((h) => nomi.includes(h)); if (i >= 0) posto[campo] = i; }
  const mancano = OBBLIGATORIE[nome].filter((c) => !(c in posto));
  if (mancano.length) return { errore: `${nome}: manca la colonna ${mancano.join(", ")}` };
  return { righe: righe.slice(1).map((r, n) => ({ riga: n + 2, ...Object.fromEntries(Object.keys(COLONNE[nome]).map((c) => [c, c in posto ? (r[posto[c]] ?? "").trim() : ""])) })) };
}

const email = (s) => { const t = String(s ?? "").replace(/ /g, " ").trim(); const m = t.match(/<([^>]+)>\s*$/); return (m ? m[1] : t.replace(/^mailto:/i, "")).trim().toLowerCase(); };
const emailValida = (e) => /^[^\s@,;]+@[^\s@.,;]+(\.[^\s@.,;]+)+$/.test(e);
const dominio = (e) => (emailValida(e) ? e.split("@")[1] : "");

function partitaIva(s) {                      // 11 cifre con la cifra di controllo giusta, altrimenti vuota
  const t = String(s ?? "").toUpperCase().replace(/^\s*IT/, "").replace(/[^0-9]/g, "");
  if (t.length !== 11) return "";
  let somma = 0;
  for (let i = 0; i < 10; i++) { let c = +t[i]; if (i % 2) { c *= 2; if (c > 9) c -= 9; } somma += c; }
  return (10 - (somma % 10)) % 10 === +t[10] ? t : "";
}
function data(s) {                            // "" se manca, null se c'è ma non si legge, altrimenti AAAA-MM-GG
  const t = String(s ?? "").trim();
  if (!t) return "";
  let m = t.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/), a, b, c;
  if (m) [, a, b, c] = m;
  else if ((m = t.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})/))) [, c, b, a] = m;
  else return null;
  const d = new Date(Date.UTC(+a, +b - 1, +c));
  return d.getUTCFullYear() === +a && d.getUTCMonth() === +b - 1 && d.getUTCDate() === +c ? d.toISOString().slice(0, 10) : null;
}
const piuGiorni = (g, n) => new Date(Date.parse(g + "T00:00:00Z") + n * 864e5).toISOString().slice(0, 10);
const it = (g) => String(g).replace(/^(\d{4})-(\d\d)-(\d\d)$/, "$3/$2/$1");      // le date escono come le legge una persona
const nomeAzienda = (s) => parola(s).replace(/[.,'’-]/g, "").replace(/\b(s ?r ?l ?s?|s ?p ?a|s ?n ?c|s ?a ?s|gmbh|ltd|sa)\b/g, "").replace(/\s+/g, " ").trim();
const haAllarme = (testo, V) => senzaAccenti(String(testo)).toLowerCase().split(/[^a-z0-9]+/).find((p) => V.inizio_parole_allarme.some((a) => p.startsWith(a))) || "";

// ---------- la stessa azienda in file diversi

function indice(tab, V) {                     // dominio aziendale -> partite IVA viste insieme a quel dominio
  const ivaDi = new Map();
  for (const r of [...tab.destinatari, ...tab.ticket, ...tab.ordini]) {
    const p = partitaIva(r.piva), d = dominio(email(r.email));
    if (p && d && !V.domini_personali.includes(d)) (ivaDi.get(d) ?? ivaDi.set(d, new Set()).get(d)).add(p);
  }
  return ivaDi;
}
function chi(r, ivaDi, V) {
  const e = email(r.email), d = dominio(e), aziendale = d && !V.domini_personali.includes(d) ? d : "", iva = ivaDi.get(aziendale) ?? new Set();
  return { email: e, dominio: aziendale, iva: partitaIva(r.piva) || (iva.size === 1 ? [...iva][0] : ""), gruppo: iva, nome: nomeAzienda(r.azienda) };
}
function legame(a, b) {                       // "si", "forse" o "no"
  if (a.iva && b.iva) return a.iva === b.iva ? "si" : "no";
  if ((!a.iva && b.iva && a.gruppo.has(b.iva)) || (!b.iva && a.iva && b.gruppo.has(a.iva))) return "forse";   // un dominio, più aziende
  if (a.dominio && a.dominio === b.dominio) return a.gruppo.size > 1 ? "forse" : "si";
  if (a.dominio && b.dominio && (a.dominio.endsWith("." + b.dominio) || b.dominio.endsWith("." + a.dominio))) return "forse";
  if (a.email && a.email === b.email) return "si";
  return a.nome && a.nome === b.nome ? "forse" : "no";                                  // solo il nome: non basta mai
}

// ---------- le regole

function regolaPermesso(voci, oggi, V) {                                                  // R3
  if (!voci.length) return { ferma: "nessun permesso registrato", chi: "marketing" };
  const v = voci.map((x) => ({ esito: V.dice_si.includes(parola(x.permesso)) ? "si" : V.dice_no.includes(parola(x.permesso)) ? "no" : "?", parola: x.permesso, fonte: parola(x.fonte), g: data(x.data) }));
  const strana = v.find((x) => x.esito === "?");
  const no = v.filter((x) => x.esito === "no"), si = v.filter((x) => x.esito === "si" && x.g && x.g <= oggi && x.fonte);
  if (no.length) {
    if (no.some((x) => !x.g)) return { ferma: "permesso negato, senza data leggibile", chi: "marketing" };
    const ultimoNo = no.map((x) => x.g).sort().pop(), dopo = si.filter((x) => x.g > ultimoNo);
    if (dopo.some((x) => V.fonti_che_riaprono.includes(x.fonte))) return strana ? { chiedi: `permesso scritto "${strana.parola}": vale sì o no?`, chi: "marketing" } : {};
    if (dopo.length) return { chiedi: `dopo il no del ${it(ultimoNo)} c'è un sì da "${dopo[0].fonte}": è il cliente che ha cambiato idea?`, chi: "marketing" };
    if (si.some((x) => x.g === ultimoNo)) return { chiedi: `sì e no nello stesso giorno (${it(ultimoNo)}): quale vale?`, chi: "marketing" };
    return { ferma: `permesso negato il ${it(ultimoNo)}`, chi: "marketing" };
  }
  if (strana) return { chiedi: `permesso scritto "${strana.parola}": vale sì o no?`, chi: "marketing" };
  if (si.length) return {};
  return { chiedi: "c'è un sì, ma senza fonte o con una data che non vale: si può provare?", chi: "marketing" };
}

function regolaOrdine(o, oggi, V) {                                                       // R5
  if (V.ordini_che_non_contano.includes(parola(o.stato))) return {};
  const p = data(o.promessa), c = data(o.consegna), rif = `ordine ${o.numero}`;
  if (p === null || c === null) return { chiedi: `${rif}: data che non si legge (${p === null ? o.promessa : o.consegna}). È in ritardo?`, chi: "ufficio ordini", rif };
  if (p === "") return { nota: `${rif}: senza data promessa, non si può dire in ritardo` };
  if (c === "" && p < oggi) return { ferma: `${rif} promesso il ${it(p)} e non consegnato`, fino: "alla consegna", chi: "ufficio ordini", rif };
  if (c && c > p && oggi <= piuGiorni(c, V.giorni_dopo_consegna)) return { ferma: `${rif} consegnato in ritardo il ${it(c)}`, fino: it(piuGiorni(c, V.giorni_dopo_consegna)), chi: "ufficio ordini", rif };
  return {};
}

function regolaTicket(t, oggi, V) {                                                       // R6
  const rif = `ticket ${t.id}`, cat = parola(t.categoria), allarme = haAllarme(t.testo, V) || haAllarme(t.categoria, V);
  const grave = V.categorie_che_fermano.includes(cat) || V.priorita_che_fermano.includes(parola(t.priorita)) || allarme;
  if (V.ticket_chiuso.includes(parola(t.stato))) {
    if (!grave) return {};
    const c = data(t.chiuso) || oggi, fino = piuGiorni(c, V.giorni_dopo_reclamo);
    return oggi <= fino ? { ferma: `${rif}: reclamo chiuso da poco`, fino: it(fino), chi: "assistenza", rif } : {};
  }
  if (grave) return { ferma: `${rif}: reclamo aperto${allarme ? ` (nel testo: "${allarme}")` : ""}`, fino: `${V.giorni_dopo_reclamo} giorni dopo la chiusura`, chi: "assistenza", rif };
  if (V.categorie_innocue.includes(cat)) return {};
  if (!t.testo.trim()) return { chiedi: `${rif}: aperto, senza categoria e senza testo. È un reclamo?`, chi: "assistenza", rif };
  return { leggere: true, rif, chi: "assistenza" };
}

// R7. L'AI può fermare, non può far passare. La sua risposta vale solo se è scritta come richiesto
// e se la prova è davvero nel testo del ticket; in ogni altro caso decide una persona.
function regolaAI(t, risposta, V) {
  const rif = `ticket ${t.id}`, domanda = `${rif}: "${t.testo.length > 90 ? t.testo.slice(0, 90) + "..." : t.testo}" È un reclamo?`;
  const base = (proposta) => ({ chiedi: `${domanda}${proposta ? ` Proposta dell'AI: ${proposta}` : ""}`, chi: "assistenza", rif });
  let r = risposta;
  if (typeof r === "string") { try { r = JSON.parse(r); } catch { return base("risposta non leggibile"); } }
  if (!r || typeof r !== "object") return base("");
  if (!["reclamo", "domanda", "richiesta_commerciale", "altro"].includes(r.tipo)) return base("risposta non prevista");
  const spoglia = (s) => parola(s).replace(/["“”«»']/g, "").replace(/\s+/g, " ").trim(), prova = spoglia(r.prova);
  const trovata = prova.length >= 3 && spoglia(t.testo).includes(prova);
  if (r.tipo === "reclamo") return { ferma: `${rif}: reclamo letto nel testo${trovata ? ` ("${prova}")` : ""}`, fino: `${V.giorni_dopo_reclamo} giorni dopo la chiusura`, chi: "assistenza", rif };
  return base(trovata ? `${r.tipo.replace("_", " ")} ("${prova}")` : "nessuna prova nel testo");
}

// Primo passo: tutto quello che ha una sola risposta giusta. Restituisce anche i testi da far leggere.
function regoleFisse(testi, oggi, exportDel, valori) {
  const V = { ...VALORI, ...(valori || {}) }, tab = {}, blocchi = [];
  for (const nome of Object.keys(COLONNE)) { const l = leggi(nome, testi[nome]); if (l.errore) blocchi.push(l.errore); tab[nome] = l.righe || []; }
  const d = data(exportDel);                                                              // R1
  if (!d) blocchi.push("manca la data in cui sono stati scaricati i file");
  else if (d > oggi || d < piuGiorni(oggi, -V.giorni_export)) blocchi.push(`i file sono del ${it(d)}: servono di oggi o di ieri`);
  const ivaDi = indice(tab, V), note = [];
  const persone = tab.destinatari.map((r) => ({ r, ...chi(r, ivaDi, V) }));
  const fatti = [
    ...tab.ordini.map((o) => ({ di: chi(o, ivaDi, V), ...regolaOrdine(o, oggi, V), regola: "R5", nome: `ordine ${o.numero}` })),
    ...tab.ticket.map((t) => ({ di: chi(t, ivaDi, V), ...regolaTicket(t, oggi, V), regola: "R6", ticket: t, nome: `ticket ${t.id}` })),
  ];
  for (const f of fatti) { if (f.nota) note.push(f.nota); if ((f.ferma || f.chiedi || f.leggere) && !persone.some((p) => legame(p, f.di) !== "no")) note.push(`${f.nome}: non è collegabile a nessun destinatario`); }
  const visti = new Set(), esiti = [];
  for (const p of persone) {
    const e = { email: p.email || p.r.email, nome: p.r.nome, azienda: p.r.azienda, responsabile: p.r.responsabile, ferma: [], chiedi: [], leggere: [] };
    esiti.push(e);
    if (!emailValida(p.email)) { e.ferma.push({ testo: "indirizzo non valido", chi: "marketing", regola: "R2" }); continue; }
    if (V.domini_interni.includes(dominio(p.email))) { e.ferma.push({ testo: "collega: non è un cliente", chi: "marketing", regola: "R2" }); continue; }
    if (visti.has(p.email)) { e.ferma.push({ testo: "doppione: già in lista", chi: "marketing", regola: "R2" }); continue; }
    visti.add(p.email);
    if (blocchi.length) { e.chiedi.push({ testo: blocchi.join("; "), chi: "marketing", regola: "R1" }); continue; }
    const perm = regolaPermesso(tab.permessi.filter((x) => email(x.email) === p.email), oggi, V);
    if (perm.ferma) e.ferma.push({ testo: perm.ferma, chi: perm.chi, regola: "R3" });
    if (perm.chiedi) e.chiedi.push({ testo: perm.chiedi, chi: perm.chi, regola: "R3" });
    for (const f of fatti) {
      const l = legame(p, f.di);
      if (l === "no" || !(f.ferma || f.chiedi || f.leggere)) continue;
      const comune = { chi: f.chi, regola: f.regola, rif: f.rif, fino: f.fino };
      if (l === "forse") e.chiedi.push({ ...comune, testo: `${f.nome}: riguarda questa azienda? (${p.gruppo.size > 1 || f.di.gruppo.size > 1 ? "stesso dominio, più partite IVA" : p.nome && p.nome === f.di.nome ? "coincide solo il nome" : "i domini si somigliano"})`, regola: "R4" });
      else if (f.ferma) e.ferma.push({ ...comune, testo: f.ferma });
      else if (f.chiedi) e.chiedi.push({ ...comune, testo: f.chiedi });
      else e.leggere.push(f.ticket.id);
    }
  }
  const daLeggere = blocchi.length ? [] : [...new Map(fatti.filter((f) => f.leggere && esiti.some((e) => e.leggere.includes(f.ticket.id))).map((f) => [f.ticket.id, { id: f.ticket.id, testo: f.ticket.testo }])).values()];
  return { blocchi, note, esiti, daLeggere, valori: V };
}

// Secondo passo: le risposte dell'AI (se ci sono) e le tre liste. Chi ha un motivo per fermarsi si ferma (R8).
function treListe(passo, risposte) {
  const liste = { invia: [], ferma: [], controlla: [] };
  for (const e of passo.esiti) {
    const ferma = [...e.ferma], chiedi = [...e.chiedi];
    for (const id of e.leggere) {
      const t = passo.daLeggere.find((x) => x.id === id), r = regolaAI(t, risposte ? risposte[id] : null, passo.valori);
      if (r.ferma) ferma.push({ testo: r.ferma, chi: r.chi, regola: "R7", fino: r.fino, rif: r.rif });
      else chiedi.push({ testo: r.chiedi, chi: r.chi, regola: "R7", rif: r.rif });
    }
    const base = { email: e.email, nome: e.nome, azienda: e.azienda, responsabile: e.responsabile }, unisci = (a, k) => [...new Set(a.map((x) => x[k]).filter(Boolean))].join(" | ");
    if (ferma.length) liste.ferma.push({ ...base, motivo: unisci(ferma, "testo"), fino_a: unisci(ferma, "fino"), decide: unisci(ferma, "chi"), regola: unisci(ferma, "regola") });
    else if (chiedi.length) liste.controlla.push({ ...base, domanda: unisci(chiedi, "testo"), decide: unisci(chiedi, "chi"), regola: unisci(chiedi, "regola") });
    else liste.invia.push(base);
  }
  return liste;
}

const cella = (v) => { let s = String(v ?? ""); if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; return /[";\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
const inCsv = (righe, colonne) => "﻿" + [colonne.join(";"), ...righe.map((r) => colonne.map((c) => cella(r[c])).join(";"))].join("\r\n") + "\r\n";
const COLONNE_LISTE = { invia: ["email", "nome", "azienda", "responsabile"], ferma: ["email", "nome", "azienda", "responsabile", "motivo", "fino_a", "decide", "regola"], controlla: ["email", "nome", "azienda", "responsabile", "domanda", "decide", "regola"] };

if (typeof module !== "undefined") module.exports = { VALORI, regoleFisse, treListe, regolaAI, inCsv, COLONNE_LISTE, partitaIva, data, righeCsv, email };
