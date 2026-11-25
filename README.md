# E-commerce CX Analytics

<sub>Il nome è quello del link stampato sul mio CV; l'analisi citata lì è [più sotto](#lanalisi-del-mio-cv). · Repo name kept so the link on my CV still works.</sub>

> **English summary (full README in Italian below):**
> - **Problem:** Before a B2B email send, the marketing team cannot see whether a contact's company has an open complaint, a late ERP order or a revoked consent sitting in separate tools.
> - **How it works:** An n8n workflow (plus a browser tester) runs 8 rules across four exports (recipients, consents, support tickets, ERP orders) and splits the list into *Send*, *Hold* (whole company by VAT/domain) and *Ask a person* — never sending emails or editing CRM records.
> - **AI guardrail & verification:** Local AI reads only uncategorised open tickets and **can only hold, never pass**. Tested on 48 dirty edge cases, 90 unit tests, 48,000 randomised sends and live n8n 2.48.7 runs; also includes the public Olist CX analysis referenced in my CV (`analisi-cv/`).

**Problema.** La newsletter parte alle 11. Chi la prepara non vede che un cliente in lista ha un reclamo aperto, uno aspetta un ordine in ritardo e uno ha ritirato il permesso: sono tre programmi diversi.

**Entra.** Quattro file: destinatari, permessi, ticket dell'assistenza, ordini del gestionale.

**Succede.** Otto regole: sette fisse, e una in cui l'AI legge i ticket aperti senza categoria. Può fermare qualcuno, non può far passare nessuno.

**Esce.** Tre liste: *Invia*, *Ferma* (motivo, fino a quando, chi decide), *Da decidere* (una domanda precisa per una persona). Non parte nessuna email e non si modifica nessun dato.

[![La pagina: cambi un dato e vedi chi si sposta da una lista all'altra](assets/pagina.png)](https://errer441122.github.io/ecommerce-cx-analytics/)

**[Provalo: cambia un dato e guarda chi si sposta](https://errer441122.github.io/ecommerce-cx-analytics/)** · [Workflow n8n](workflows/prima-dell-invio.n8n.json) · [Le regole, a parole](docs/regole.md) · [L'analisi del mio CV](#lanalisi-del-mio-cv)

> **Dati inventati**: 48 destinatari, ognuno un caso sporco. La lettura dell'AI e il workflow n8n sono stati eseguiti davvero, il 25 novembre 2026. In un'azienda non è ancora stato usato.

## Le otto regole

| Regola | Cosa succede |
| --- | --- |
| **R1 File** | Un file manca, è vuoto o non è di oggi o di ieri: non passa nessuno |
| **R2 Indirizzo** | Non valido, collega o doppione: fermo |
| **R3 Permesso** | Serve un sì con fonte e data. Un no ferma. Un sì rimesso a mano dopo un no lo decide una persona |
| **R4 Stessa azienda** | Partita IVA valida o dominio aziendale. Il solo nome non basta mai |
| **R5 Ordine** | In ritardo: ferma tutta l'azienda fino alla consegna. Consegnato in ritardo: altri 7 giorni |
| **R6 Ticket** | Reclamo aperto: ferma tutta l'azienda. Chiuso da poco: 7 giorni. Richiesta di catalogo: non ferma |
| **R7 Testo da leggere** | Ticket aperto senza categoria: lo legge l'AI. Se è un reclamo ferma, altrimenti propone e decide una persona |
| **R8 Decisione** | Un motivo basta per fermare. Con un dubbio decide una persona. Passa solo chi non ha né motivi né dubbi |

Il perché di ogni regola, e le stesse regole su HubSpot, Salesforce o un foglio: [`docs/regole.md`](docs/regole.md).

## Cosa non fa mai

- Non scrive ai clienti e non modifica CRM, programma di email o gestionale.
- Non cambia un permesso: se due fonti si contraddicono, lo chiede.
- Non unisce due aziende per il solo nome.
- Non fa passare nessuno per merito dell'AI.

## Prove

**Casi sporchi: 48 su 48.** Ogni destinatario dell'esempio è un caso ([`casi/attesi.csv`](casi/attesi.csv)): partita IVA con una cifra in meno, due aziende con lo stesso dominio, sì e no lo stesso giorno, data 31/02, reclamo registrato solo con il nome, un ticket che prova a dare ordini all'AI. Altri 42 controlli provano file mancanti, vecchi, con altri separatori e dieci risposte sbagliate dell'AI. In tutto [90 test](tests/regole.test.mjs), a ogni modifica. **48.000 destinatari generati a caso** in 3.000 invii con file sporchi: un [controllo scritto senza guardare le regole](tests/casuali.mjs) non ha trovato nessuno passato con un no, un reclamo aperto o un ordine in ritardo. Il caso del dominio con due partite IVA ha trovato un errore vero nella prima versione: un contatto passava e non doveva.

**n8n 2.48.7, eseguito davvero** ([dettagli](prove/n8n-2026-11-25.md)):

| Prova | Invia | Ferma | Da decidere |
| --- | ---: | ---: | ---: |
| Tutti i file, AI accesa | 12 | 21 | 15 |
| AI spenta | 12 | 19 | 17 |
| Manca il file dei ticket | 0 | 3 | 45 |
| File di tre giorni prima | 0 | 3 | 45 |

**L'AI, su 30 testi difficili** ([testi e risposte](ai/risultati.json)), letti da un modello piccolo sul mio computer (qwen3.5:4b), quindi il testo non esce dall'azienda:

| | |
| --- | ---: |
| Reclami fermati subito | 12 su 14 |
| Reclami non visti, che legge una persona | 2 |
| Domande proposte giuste | 10 su 10 |
| Fermati per errore | 0 |
| Passati senza una persona | 0 |

Se l'AI potesse far passare qualcuno da sola, 4 testi su 30 sarebbero passati per errore. Per questo può solo fermare. [Perché non uso il suo punteggio di sicurezza](ai/prima-prova.md).

## Dove si ferma

- Fotografa il momento dei file: un reclamo arrivato dopo non lo vede. Va fatto poco prima dell'invio.
- Un invio alla volta. Se più persone preparano invii insieme serve un CRM condiviso.
- Le parole di allarme sono caute: "non è un reclamo" ferma lo stesso.
- Se CRM, assistenza e gestionale sono già collegati, le regole R5 e R6 diventano filtri nel CRM e il workflow serve solo per i casi dubbi.
- L'email interna con le tre liste non è stata spedita nelle prove: il nodo è stato sostituito per leggere gli allegati.

## Usarlo

1. In n8n: **Workflows → Import from File** → [`prima-dell-invio.n8n.json`](workflows/prima-dell-invio.n8n.json).
2. Nel nodo **Valori da cambiare**: i tuoi domini, i giorni, l'indirizzo del modello AI (Ollama o un servizio compatibile con OpenAI).
3. Nel nodo **Email interna**: mittente, destinatario e SMTP. Poi apri il modulo e carica i quattro file.

Senza n8n: la [pagina](https://errer441122.github.io/ecommerce-cx-analytics/#prova) fa lo stesso con i tuoi file, nel browser e senza AI.

## Perché due regole sono così

- **Un ordine in ritardo ferma.** Nell'analisi del mio CV, su 95.639 recensioni vere, è soddisfatto l'82,7% di chi riceve in tempo e il 26,7% di chi riceve in ritardo.
- **Una nota di credito da sola no.** Su due anni di un vero grossista, chi ha appena reso merce riordina entro 90 giorni nel 79% dei casi, i clienti simili nel 75%: [numeri](prove/nota-di-credito.md).

## L'analisi del mio CV

| Cosa dice il CV | Dove si trova |
| --- | --- |
| Circa 95.000 recensioni vere (Olist): la consegna in ritardo è il fattore più legato all'insoddisfazione, 27% di recensioni positive contro 83% | [Analisi completa](analisi-cv/reports/cx_driver_analysis.md), "Delivery-SLA cohort": 95.639 recensioni, 26,7% contro 82,7% |
| Test statistici, proxy NPS, regressione logistica | Nella stessa analisi. Olist non ha una domanda NPS: 5 stelle valgono promotore, 4 neutro, 3 o meno detrattore |
| Brief per gli stakeholder | [Customer satisfaction brief](analisi-cv/reports/customer_satisfaction_brief.md), per stato e categoria |

## Come è fatto

Studente di Digital Marketing, non sviluppatore. Workflow, regole e test sono stati costruiti con assistenti AI. Licenza MIT per il codice; dati Olist CC BY-NC-SA 4.0 (portfolio non commerciale), UCI *Online Retail II* CC BY 4.0.
