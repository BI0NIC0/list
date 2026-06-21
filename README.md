# Lista unificata automatica

Questo repository genera e pubblica ogni giorno una lista unica a partire da più liste remote.

Il sistema:

- scarica tutte le sorgenti configurate;
- estrae gli URL;
- normalizza i domini;
- elimina i duplicati;
- esegue controlli tecnici di raggiungibilità;
- applica esclusioni manuali e automatiche;
- ordina alfabeticamente il risultato;
- pubblica una sola lista finale sempre allo stesso indirizzo.

## Link della lista finale

```text
https://raw.githubusercontent.com/BI0NIC0/list/main/lista.txt
```

Il collegamento non cambia: mostra sempre l'ultima versione generata.

---

## Come vengono raccolti e normalizzati gli URL

Le sorgenti remote sono indicate in `sources.txt`, una per riga.

Durante l'elaborazione:

- le righe vuote e quelle che iniziano con `#` vengono ignorate;
- vengono estratti soltanto collegamenti HTTP e HTTPS validi;
- HTTP e HTTPS sono considerati equivalenti ai fini della deduplicazione;
- `www` e non `www` sono considerati equivalenti;
- viene mantenuta una sola voce per dominio;
- frammenti, slash finali e percorsi duplicati dello stesso dominio non generano voci separate;
- i domini tecnici delle piattaforme che ospitano le liste, i tracker e i metadati noti vengono ignorati;
- il risultato viene ordinato alfabeticamente per dominio.

## Come aggiungere una sorgente

1. Apri `sources.txt`.
2. Seleziona `Edit this file`.
3. Aggiungi il nuovo indirizzo su una riga separata.
4. Salva con `Commit changes`.

Esempio:

```text
https://esempio.it/lista.txt
https://esempio.net/elenco/raw
```

La modifica avvia automaticamente GitHub Actions e rigenera la lista.

---

## Protezione in caso di sorgenti temporaneamente non raggiungibili

Ogni sorgente viene scaricata con più tentativi e un tempo massimo di attesa.

Se una sorgente fallisce temporaneamente:

- le altre sorgenti continuano a essere elaborate;
- l'intera esecuzione non viene annullata;
- la lista precedente viene riutilizzata come protezione contro la perdita improvvisa di domini;
- l'errore viene registrato in `last-run.txt`.

Questa protezione serve a evitare che un timeout momentaneo o un problema del server remoto svuoti o riduca impropriamente la lista finale.

---

## Blacklist manuale

I domini verificati manualmente come non utilizzabili possono essere inseriti in `blacklist.txt`, uno per riga.

Inserire soltanto il dominio, senza protocollo, percorso o `www`.

Esempio:

```text
esempio.it
altro-esempio.net
```

Per ogni dominio inserito vengono escluse automaticamente:

- la versione HTTP e quella HTTPS;
- la versione con e senza `www`;
- gli eventuali sottodomini;
- le copie recuperate dalla lista precedente.

La blacklist manuale ha sempre precedenza sugli altri controlli.

È necessaria soprattutto per i casi che dipendono dalla rete o dal Paese da cui si effettua la verifica: il runner GitHub può infatti vedere una pagina diversa da quella mostrata a un utente collegato dall'Italia.

---

## Controllo tecnico automatico

Dopo aver generato la lista provvisoria, `check_sites.py` controlla i domini che non sono già presenti nella blacklist manuale.

Il controllo usa richieste parallele, con timeout limitato, per non rallentare eccessivamente il workflow.

### Errori tecnici

Un dominio viene classificato come `ERRORE` quando viene rilevato, ad esempio:

- dominio non risolvibile tramite DNS;
- connessione non riuscita;
- timeout oltre il limite previsto;
- certificato SSL/TLS non valido o non verificabile;
- codice HTTP `404`, `410` o `451`;
- codice HTTP `5xx`, compresi gli errori dei servizi proxy o CDN;
- pagina che segnala dominio inesistente, scaduto, sospeso o non disponibile;
- pagina che segnala server di origine non raggiungibile;
- risposta composta soltanto da un messaggio di errore minimo riconosciuto;
- pagina di blocco riconoscibile dal testo restituito.

### Avvisi tecnici

Un dominio viene classificato come `ATTENZIONE`, ma non escluso automaticamente, quando viene rilevato, ad esempio:

- codice HTTP `400`, `401`, `403`, `405`, `408`, `409`, `425` o `429`;
- protezione anti-bot o verifica del browser;
- pagina temporaneamente non disponibile;
- modalità manutenzione;
- reindirizzamento verso un dominio differente;
- risposta insolitamente breve.

Gli avvisi non vengono trattati come errori perché possono dipendere dal comportamento del runner GitHub, da sistemi anti-bot o da limitazioni temporanee che non impediscono necessariamente l'uso normale tramite browser o applicazione.

### Limiti del controllo

Il controllo tecnico non certifica che un sito sia effettivamente utilizzabile dall'Italia.

In particolare:

- alcuni blocchi possono essere applicati soltanto da operatori o DNS italiani;
- un sito può rispondere correttamente al runner GitHub ma non all'utente;
- un sistema anti-bot può bloccare il controllo automatico ma consentire l'accesso da browser;
- un errore temporaneo non significa necessariamente che il dominio debba essere eliminato definitivamente.

Per questo il sistema combina controllo automatico e blacklist manuale.

---

## Esclusione automatica prudenziale

Lo stato dei controlli viene conservato in `site-health-state.json`.

Un dominio entra in `auto-excluded.txt` soltanto dopo due esecuzioni consecutive classificate come `ERRORE`.

La logica è:

- primo errore consecutivo: il dominio viene segnalato nel rapporto, ma resta nella lista;
- secondo errore consecutivo: il dominio viene aggiunto alle esclusioni automatiche;
- controllo successivo positivo o classificato come semplice avviso: il conteggio degli errori viene azzerato;
- se il dominio torna raggiungibile, viene rimosso automaticamente da `auto-excluded.txt`.

Questa soglia riduce il rischio di eliminare domini a causa di un singolo timeout, di una manutenzione breve o di un problema momentaneo del server.

### Persistenza dello storico

Prima del controllo il workflow crea una copia temporanea di `site-health-state.json`.

Dopo il controllo:

- i risultati appena ottenuti hanno sempre precedenza;
- gli stati con almeno un errore consecutivo vengono conservati anche se il dominio scompare temporaneamente dalle sorgenti;
- le esclusioni automatiche restano memorizzate durante l’assenza;
- gli stati senza errori pendenti non vengono mantenuti inutilmente;
- quando il dominio ricompare, il conteggio riparte dal valore conservato;
- un risultato `OK` o `ATTENZIONE` azzera il conteggio;
- un nuovo `ERRORE` continua invece il conteggio precedente.

In questo modo un dominio non può rientrare nella lista soltanto perché è scomparso temporaneamente dalle sorgenti e poi è ricomparso.

La copia temporanea viene eliminata prima del commit e non viene pubblicata nel repository.

`filter_blacklist.py` applica alla lista finale, nell'ordine:

1. la blacklist manuale;
2. le esclusioni automatiche persistenti.

---

## Rapporti generati

### `last-run.txt`

Contiene il riepilogo dell'ultima esecuzione:

- data e ora UTC;
- numero di sorgenti configurate, riuscite e fallite;
- utilizzo eventuale della lista precedente;
- domini configurati nella blacklist manuale;
- domini configurati nelle esclusioni automatiche;
- numero di voci escluse;
- numero finale di siti unici;
- numero di siti controllati tecnicamente;
- avvisi ed errori rilevati;
- riferimento al rapporto tecnico.

### `site-health.txt`

Contiene un rapporto leggibile dell'ultimo controllo:

- numero di siti controllati;
- numero di siti già esclusi manualmente e quindi non verificati;
- siti classificati come `OK`, `ATTENZIONE` o `ERRORE`;
- motivazione delle anomalie;
- numero di errori consecutivi per ciascun dominio anomalo;
- numero di domini auto-esclusi.

### `site-health-state.json`

Conserva lo stato tecnico tra un'esecuzione e la successiva, compresi:

- numero di errori consecutivi;
- ultimo livello rilevato;
- ultima motivazione;
- data e ora dell'ultimo controllo.

### `auto-excluded.txt`

È generato automaticamente e contiene i domini che hanno raggiunto la soglia prevista di errori consecutivi.

Non deve essere compilato manualmente.

---

## Ordine completo del workflow

Durante ogni esecuzione il sistema:

1. scarica il repository;
2. configura Python;
3. legge le sorgenti da `sources.txt`;
4. scarica e unisce le liste remote;
5. normalizza e deduplica gli URL;
6. usa la lista precedente se una sorgente è temporaneamente irraggiungibile;
7. salva temporaneamente lo stato tecnico precedente;
8. esegue il controllo tecnico sui domini non già esclusi manualmente;
9. unisce i nuovi risultati con gli errori pendenti dei domini temporaneamente assenti;
10. ricostruisce `site-health-state.json` e `auto-excluded.txt`;
11. applica blacklist manuale ed esclusioni automatiche;
12. ordina e pubblica `lista.txt`;
13. aggiorna `last-run.txt` e `site-health.txt`;
14. elimina la copia temporanea dello stato;
15. crea un commit automatico soltanto se uno dei file generati è cambiato.

## Quando viene eseguito

Il workflow parte:

- quando cambia `sources.txt`;
- quando cambia `blacklist.txt`;
- quando cambia `merge_lists.py`;
- quando cambia `check_sites.py`;
- quando cambia `filter_blacklist.py`;
- quando cambia il workflow stesso;
- automaticamente ogni giorno alle `03:17 UTC`;
- manualmente dalla scheda `Actions` tramite `Run workflow`.

In Italia l'esecuzione giornaliera corrisponde indicativamente:

- alle `05:17` durante l'ora legale;
- alle `04:17` durante l'ora solare.

---

## File principali

| File | Funzione |
|---|---|
| `sources.txt` | Elenco delle liste remote da scaricare |
| `blacklist.txt` | Domini esclusi manualmente |
| `merge_lists.py` | Download, estrazione, normalizzazione e deduplicazione |
| `check_sites.py` | Controllo tecnico e gestione dello storico |
| `filter_blacklist.py` | Applicazione delle esclusioni manuali e automatiche |
| `lista.txt` | Lista finale pubblicata |
| `last-run.txt` | Riepilogo dell'ultima esecuzione |
| `site-health.txt` | Rapporto tecnico leggibile |
| `site-health-state.json` | Stato persistente degli errori consecutivi |
| `auto-excluded.txt` | Domini esclusi automaticamente |
| `.github/workflows/aggiorna-lista.yml` | Automazione GitHub Actions |

---

## Nota d'uso

La presenza di un indirizzo nella lista non certifica disponibilità, sicurezza o liceità dei contenuti.

L'utilizzo dei servizi deve avvenire nel rispetto della legge e delle condizioni applicabili.
