# Lista unificata automatica

Questo repository genera ogni giorno una lista unica a partire da più liste remote. Gli URL vengono normalizzati, deduplicati e ordinati alfabeticamente per dominio; al termine vengono rimossi anche i domini inseriti nella blacklist locale.

## Link della lista finale

```text
https://raw.githubusercontent.com/BI0NIC0/list/main/lista.txt
```

Il collegamento rimane invariato e mostra sempre l'ultima versione generata.

## Come aggiungere una sorgente

1. Apri `sources.txt`.
2. Seleziona `Edit this file`.
3. Aggiungi l'indirizzo della nuova lista su una riga separata.
4. Salva con `Commit changes`.

Esempio:

```text
https://esempio.it/lista.txt
https://esempio.net/lista/raw
```

Le righe vuote e quelle che iniziano con `#` vengono ignorate. La modifica avvia automaticamente GitHub Actions e rigenera `lista.txt`.

## Come escludere un dominio

I domini verificati manualmente come non utilizzabili devono essere inseriti in `blacklist.txt`, uno per riga e senza protocollo, percorso o `www`.

Esempio:

```text
esempio.it
altro-esempio.net
```

Per ogni dominio inserito vengono escluse automaticamente:

- la versione HTTP e quella HTTPS;
- la versione con e senza `www`;
- gli eventuali sottodomini;
- le copie presenti nella lista precedente usata come protezione temporanea.

Le righe vuote e quelle che iniziano con `#` vengono ignorate. Anche una modifica a `blacklist.txt` avvia automaticamente l'aggiornamento.

La blacklist è volutamente manuale: un runner GitHub può collegarsi da un Paese diverso dall'Italia e non rilevare blocchi, pagine sostitutive o altri problemi visibili sulla connessione dell'utente.

## Aggiornamento automatico

Durante ogni esecuzione il sistema:

1. scarica tutte le sorgenti configurate;
2. estrae e normalizza gli URL;
3. considera equivalenti HTTP/HTTPS e `www`/non `www`;
4. mantiene una sola voce per dominio;
5. recupera la lista precedente se una sorgente è temporaneamente irraggiungibile;
6. applica `blacklist.txt`;
7. ordina alfabeticamente il risultato;
8. aggiorna `lista.txt` e `last-run.txt`.

Il workflow viene eseguito:

- quando cambia `sources.txt`;
- quando cambia `blacklist.txt`;
- quando cambia `merge_lists.py`;
- quando cambia `filter_blacklist.py`;
- quando cambia il workflow;
- ogni giorno alle 03:17 UTC, cioè alle 05:17 con l'ora legale italiana e alle 04:17 con l'ora solare;
- manualmente dalla scheda `Actions` tramite `Run workflow`.

## Controllo dell'ultimo aggiornamento

`last-run.txt` riporta:

- data e ora UTC;
- numero di sorgenti riuscite e non raggiungibili;
- numero di domini configurati ed esclusi tramite blacklist;
- numero finale di siti unici;
- eventuale utilizzo della lista precedente come protezione;
- eventuali errori temporanei delle sorgenti.

## File del repository

- `sources.txt`: elenco delle liste remote da scaricare.
- `blacklist.txt`: domini verificati manualmente da escludere.
- `merge_lists.py`: scarica, normalizza, unisce e ordina le sorgenti.
- `filter_blacklist.py`: rimuove dalla lista i domini esclusi e aggiorna il riepilogo.
- `lista.txt`: lista finale pubblicata.
- `last-run.txt`: riepilogo dell'ultima esecuzione.
- `.github/workflows/aggiorna-lista.yml`: automazione giornaliera e su modifica.

## Nota d'uso

La presenza di un indirizzo nella lista non certifica disponibilità, sicurezza o liceità dei contenuti. L'utilizzo dei servizi deve avvenire nel rispetto della legge e delle condizioni applicabili.
