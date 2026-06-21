# Lista unificata automatica

Questo repository genera ogni giorno una lista unica a partire da due o più liste remote, normalizzando gli URL ed eliminando i duplicati.

## Configurazione

1. Apri `sources.txt`.
2. Inserisci un URL sorgente per riga.
3. Apri la scheda **Actions**.
4. Seleziona **Aggiorna lista unificata**.
5. Premi **Run workflow** per il primo aggiornamento.

Il workflow viene poi eseguito automaticamente ogni giorno alle **03:17 UTC**.

## Collegamento finale

Dopo il primo aggiornamento, il file da usare è:

```text
https://raw.githubusercontent.com/BI0NIC0/list/main/lista.txt
```

Il repository deve essere pubblico affinché applicazioni esterne possano leggere il collegamento Raw senza autenticazione.

## File

- `sources.txt`: indirizzi delle liste sorgente.
- `merge_lists.py`: scarica, normalizza e unisce le liste.
- `lista.txt`: risultato finale senza duplicati.
- `last-run.txt`: data e ora dell'ultimo aggiornamento riuscito.
- `.github/workflows/aggiorna-lista.yml`: automazione giornaliera.
