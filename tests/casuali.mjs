// Prove casuali: file sporchi generati a caso, e un controllo scritto senza guardare le regole.
//   node tests/casuali.mjs
import { createRequire } from "node:module";
const R = createRequire(import.meta.url)("../docs/regole.js");
let seme = 7; const rnd = () => (seme = (seme * 1103515245 + 12345) % 2147483648) / 2147483648, scegli = (a) => a[Math.floor(rnd() * a.length)];
const iva = (n) => { const b = String(n).padStart(7, "0") + "000"; let s = 0; for (let i = 0; i < 10; i++) { let c = +b[i]; if (i % 2) { c *= 2; if (c > 9) c -= 9; } s += c; } return b + ((10 - (s % 10)) % 10); };
const sporca = (e) => scegli([e, e.toUpperCase(), "  " + e, e + " ", `Nome <${e}>`, `"Cognome, Nome" <${e}>`, "mailto:" + e]);
const sporcaIva = (p) => scegli([p, "IT" + p, "IT " + p, p.slice(0, 3) + " " + p.slice(3), p.slice(0, 5) + "." + p.slice(5)]);
const q = (x) => (/[;"\n]/.test(x) ? `"${x.replace(/"/g, '""')}"` : x), csv = (t, r) => [t, ...r].map((x) => x.map(q).join(";")).join(scegli(["\n", "\r\n"])) + "\n";
const giorno = (n) => new Date(Date.UTC(2026, 10, 25) + n * 864e5).toISOString().slice(0, 10), it = (g) => scegli([g, g.split("-").reverse().join("/"), g.split("-").reverse().join(".")]);
let persone = 0, invia = 0, problemi = [];
for (let giro = 0; giro < 3000; giro++) {
  const aziende = Array.from({ length: 8 }, (_, i) => ({ dom: `azienda${i}.example`, piva: iva(100 + giro * 10 + i), nome: `Azienda ${String.fromCharCode(65 + i)} Srl` }));
  const dest = [], perm = [], tick = [], ord = [], vero = [];
  for (let i = 0; i < 16; i++) {
    const a = scegli(aziende), personale = rnd() < 0.15, email = personale ? `p${i}@gmail.com` : `p${i}@${a.dom}`, conIva = rnd() < 0.5;
    dest.push([sporca(email), "N" + i, a.nome, conIva ? sporcaIva(a.piva) : "", ""]);
    const voci = []; for (let k = 0; k < Math.floor(rnd() * 3); k++) voci.push({ si: rnd() < 0.7, g: giorno(-Math.floor(rnd() * 300)), fonte: scegli(["modulo web", "firma in fiera", "modifica CRM", "import"]) });
    for (const v of voci) perm.push([sporca(email), scegli(v.si ? ["sì", "SI", "yes", "true"] : ["no", "revocato", "NEGATO", "unsubscribed"]), v.fonte, it(v.g)]);
    vero.push({ email, a, personale, conIva, voci });
  }
  for (let k = 0; k < Math.floor(rnd() * 5); k++) {
    const a = scegli(aziende), aperto = rnd() < 0.6, modo = scegli(["dominio", "iva", "entrambi"]);
    tick.push([`T${k}`, modo === "iva" ? "" : sporca(`x${k}@${a.dom}`), a.nome, modo === "dominio" ? "" : sporcaIva(a.piva), aperto ? scegli(["Aperto", "In lavorazione", "open"]) : "Chiuso", "", "Reclamo", "", aperto ? "" : it(giorno(-Math.floor(rnd() * 20))), "testo; con\n\"a capo\""]);
    tick[tick.length - 1].v = { a, aperto, modo };
  }
  for (let k = 0; k < Math.floor(rnd() * 5); k++) { const a = scegli(aziende), p = giorno(-Math.floor(rnd() * 30) + 10), cons = rnd() < 0.5; ord.push([`${k}`, a.nome, sporcaIva(a.piva), it(p), cons ? it(giorno(-12)) : "", "confermato"]); ord[ord.length - 1].v = { a, p, cons }; }
  const testi = { destinatari: csv(["Email", "Nome", "Azienda", "Partita IVA", "Responsabile"], dest), permessi: csv(["email", "consenso", "fonte", "data"], perm.length ? perm : [["z@z.example", "no", "x", "2026-01-01"]]),
    ticket: csv(["ID", "Richiedente", "Azienda", "Partita IVA", "Stato", "Priorità", "Categoria", "Aperto il", "Chiuso il", "Testo"], tick), ordini: csv(["Ordine", "Cliente", "Partita IVA", "Data promessa", "Data consegna", "Stato"], ord) };
  const passo = R.regoleFisse(testi, "2026-11-25", "2026-11-25"), l = R.treListe(passo, null), ok = new Set(l.invia.map((x) => x.email));
  if (passo.blocchi.length) { problemi.push(["blocco", passo.blocchi]); continue; }
  if (Object.values(l).flat().length !== dest.length) problemi.push(["persi", giro]);
  for (const v of vero) {
    persone++; if (!ok.has(v.email)) continue; invia++;
    // 1. chi ha detto no per ultimo non passa; serve almeno un sì
    const no = v.voci.filter((x) => !x.si).map((x) => x.g).sort().pop(), si = v.voci.filter((x) => x.si);
    if (!si.length) problemi.push(["passa senza un sì", giro, v.email]);
    if (no && !si.some((x) => x.g > no && ["modulo web", "firma in fiera"].includes(x.fonte))) problemi.push(["passa dopo un no", giro, v.email, v.voci]);
    // 2. un reclamo aperto della sua azienda lo ferma, se l'azienda si può riconoscere
    for (const t of tick) if (t.v.aperto && t.v.a === v.a) {
      const perIva = v.conIva && t.v.modo !== "dominio", perDominio = !v.personale && t.v.modo !== "iva";
      if (perIva || perDominio) problemi.push(["passa con un reclamo aperto", giro, v.email, t.v.modo]);
    }
    // 3. un ordine in ritardo della sua azienda lo ferma
    for (const o of ord) if (o.v.a === v.a && v.conIva && !o.v.cons && o.v.p < "2026-11-25") problemi.push(["passa con un ordine in ritardo", giro, v.email]);
  }
}
console.log(`${persone} destinatari, ${invia} passati, ${problemi.length} errori`);
if (problemi.length) { console.log(problemi.slice(0, 8)); process.exit(1); }
