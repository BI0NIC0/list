# Lista unificata automatica

Questo repository genera ogni giorno una lista unica a partire da una o più liste remote, normalizzando gli URL ed eliminando i duplicati.

## Link da aprire sul browser

```text
https://raw.githubusercontent.com/BI0NIC0/list/main/lista.txt
```

Il file contiene la lista finale aggiornata, con un solo indirizzo per ciascun sito.

## Come aggiungere altre liste

1. Apri il file `sources.txt`.
2. Seleziona **Edit this file**.
3. Aggiungi il nuovo indirizzo su una nuova riga.
4. Premi **Commit changes** per salvare.

Esempio:

```text
https://pastebin.com/raw/KgQ4jTy6
https://www.epgitalia.tv/listaveezie
https://esempio.it/altra-lista.txt
```

Puoi aggiungere tutte le sorgenti necessarie, sempre una per riga. Le righe vuote e quelle che iniziano con `#` vengono ignorate.

Quando `sources.txt` viene modificato, GitHub Actions avvia automaticamente l'aggiornamento, confronta tutte le sorgenti, elimina i siti duplicati e rigenera `lista.txt`.

## Aggiornamento automatico

Ogni giorno il sistema riscarica da capo tutte le liste indicate in `sources.txt`. Se una sorgente aggiunge, rimuove o modifica un sito, il cambiamento viene riportato automaticamente nella nuova versione di `lista.txt`.

Il workflow viene eseguito:

- ogni volta che viene modificato `sources.txt`;
- automaticamente ogni giorno alle **03:17 UTC**;
- alle **05:17 in Italia durante l'ora legale**;
- alle **04:17 in Italia durante l'ora solare**.

Il link della lista finale non cambia: mostra sempre l'ultima versione generata.

Per avviare manualmente un aggiornamento:

1. Apri la scheda **Actions**.
2. Seleziona **Aggiorna lista unificata**.
3. Premi **Run workflow**.

## File del repository

- `sources.txt`: elenco delle liste sorgente, una per riga.
- `merge_lists.py`: scarica, normalizza e unisce tutte le sorgenti.
- `lista.txt`: lista finale senza siti duplicati.
- `last-run.txt`: data, numero di sorgenti e numero di siti dell'ultimo aggiornamento.
- `.github/workflows/aggiorna-lista.yml`: automazione giornaliera.
