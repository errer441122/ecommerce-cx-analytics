# Le regole, a parole

Sette regole fisse e una sola domanda all'AI. Parole e numeri si cambiano nel nodo **Valori da cambiare** (in n8n) o in cima a [`regole.js`](regole.js).

| Regola | Cosa succede | Perché |
| --- | --- | --- |
| **R1 File** | Se un file manca, è vuoto, non ha le colonne o non è di oggi o di ieri, non passa nessuno | Un controllo su dati vecchi è peggio di nessun controllo: dà sicurezza senza averla |
| **R2 Indirizzo** | Indirizzo non valido, collega o doppione: fermo. Maiuscole, spazi e `Nome <indirizzo>` si puliscono da soli | Una persona, una riga |
| **R3 Permesso** | Serve un sì con fonte e data. Un no ferma. Un sì arrivato dopo un no vale solo se viene da una fonte del cliente (modulo web, doppia conferma, firma in fiera); se qualcuno lo ha cambiato a mano, decide una persona | L'ultima modifica nel CRM non è per forza la volontà del cliente |
| **R4 Stessa azienda** | Stessa partita IVA valida, oppure stesso dominio aziendale. Il solo nome, un dominio con più partite IVA o un sottodominio non bastano: decide una persona. Gmail e simili valgono per la persona, mai per l'azienda | Un reclamo di un collega riguarda tutta l'azienda; un omonimo no |
| **R5 Ordine** | Promessa scaduta e non consegnato: ferma tutta l'azienda fino alla consegna. Consegnato in ritardo: ferma altri 7 giorni. Annullati e resi non contano. Una data illeggibile la guarda una persona | [Dai dati reali](../analisi-cv/reports/cx_driver_analysis.md): è soddisfatto l'82,7% di chi riceve in tempo e il 26,7% di chi riceve in ritardo |
| **R6 Ticket** | Reclamo aperto (per categoria, priorità o parole come "rotto" e "rimborso"): ferma tutta l'azienda. Chiuso da meno di 7 giorni: ferma fino a quella data. "Richiesta catalogo" e simili non fermano | Chi aspetta una risposta non deve ricevere una promozione |
| **R7 Testo da leggere** | Solo i ticket aperti senza categoria e senza parole di allarme vanno all'AI. Se legge un reclamo, ferma. In ogni altro caso propone, e decide una persona | **L'AI può fermare, non può far passare** |
| **R8 Decisione** | Un solo motivo per fermarsi basta. Con un dubbio decide una persona. Passa solo chi non ha né motivi né dubbi | Un'email in meno costa poco, una sbagliata può costare il cliente |

## Cosa non ferma, e perché

Una nota di credito già fatta, da sola, non ferma nessuno. Su due anni di vendite di un vero grossista, chi ha reso merce ha riordinato almeno quanto i clienti simili: [numeri e calcolo](../prove/nota-di-credito.md).

## Cosa non fa mai

- Non manda email ai clienti e non scrive nel CRM, nel programma di email o nel gestionale: legge quattro file e ne restituisce tre.
- Non cambia un permesso: se due fonti si contraddicono, lo chiede.
- Non unisce due aziende per il solo nome.
- Non fa passare nessuno per merito dell'AI.

## Le stesse regole su altri programmi

Entrano file CSV, quindi il programma di partenza conta poco. Se i dati sono già collegati, le regole diventano filtri:

| | HubSpot | Salesforce | Un altro CRM o un foglio |
| --- | --- | --- | --- |
| R3 Permesso | Proprietà con fonte e data, storico delle modifiche | Consenso sul contatto o oggetto Individual | Colonne permesso, fonte, data |
| R4 Azienda | Associazione contatto-azienda | Account | Partita IVA e dominio |
| R5 Ordine | Dal gestionale: serve un'integrazione o il file | Idem | Il file del gestionale |
| R6 Ticket | Ticket associati all'azienda | Case | Il file dell'assistenza |
| R8 Decisione | Tre elenchi, uno da escludere dall'invio | Tre campagne o elenchi | Tre fogli |
