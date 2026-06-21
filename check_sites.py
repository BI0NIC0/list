from __future__ import annotations

import socket
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LIST_FILE = Path("lista.txt")
REPORT_FILE = Path("site-health.txt")
LAST_RUN_FILE = Path("last-run.txt")
TIMEOUT_SECONDS = 12
MAX_WORKERS = 8


def read_urls() -> list[str]:
    if not LIST_FILE.exists():
        raise RuntimeError("File lista.txt non trovato")

    return [
        line.strip()
        for line in LIST_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def check_url(url: str) -> tuple[str, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )

    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", 200)
            response.read(1024)
    except HTTPError as error:
        status = error.code
    except (socket.timeout, TimeoutError):
        return url, "ERRORE", f"timeout oltre {TIMEOUT_SECONDS} secondi"
    except ssl.SSLError as error:
        return url, "ERRORE", f"errore SSL: {error}"
    except URLError as error:
        reason = error.reason
        if isinstance(reason, socket.gaierror):
            detail = f"errore DNS: {reason}"
        elif isinstance(reason, socket.timeout):
            detail = f"timeout oltre {TIMEOUT_SECONDS} secondi"
        elif isinstance(reason, ssl.SSLError):
            detail = f"errore SSL: {reason}"
        else:
            detail = f"connessione non riuscita: {reason}"
        return url, "ERRORE", detail
    except Exception as error:
        return url, "ERRORE", f"errore inatteso: {error}"

    if status >= 500 or status in {404, 410, 451}:
        return url, "ERRORE", f"HTTP {status}"

    if status >= 400:
        return url, "ATTENZIONE", f"HTTP {status}"

    return url, "OK", f"HTTP {status}"


def update_last_run(total: int, warnings: int, errors: int) -> None:
    if not LAST_RUN_FILE.exists():
        return

    prefixes = (
        "Siti sottoposti a controllo tecnico:",
        "Avvisi tecnici:",
        "Errori tecnici:",
        "Rapporto tecnico:",
    )
    lines = [
        line
        for line in LAST_RUN_FILE.read_text(encoding="utf-8").splitlines()
        if not line.startswith(prefixes)
    ]
    lines.extend(
        [
            f"Siti sottoposti a controllo tecnico: {total}",
            f"Avvisi tecnici: {warnings}",
            f"Errori tecnici: {errors}",
            f"Rapporto tecnico: {REPORT_FILE.name}",
        ]
    )

    LAST_RUN_FILE.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    urls = read_urls()
    results: list[tuple[str, str, str]] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_url, url) for url in urls]
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: item[0].casefold())
    warnings = [item for item in results if item[1] == "ATTENZIONE"]
    errors = [item for item in results if item[1] == "ERRORE"]
    ok_count = len(results) - len(warnings) - len(errors)

    report = [
        f"Controllo UTC: {datetime.now(timezone.utc).isoformat()}",
        f"Siti controllati: {len(results)}",
        f"OK: {ok_count}",
        f"Attenzione: {len(warnings)}",
        f"Errori: {len(errors)}",
        "Rimozione automatica: no",
        "Nota: il risultato dipende dalla rete del runner GitHub e può differire da quello visibile in Italia.",
        "",
        "Anomalie rilevate:",
    ]

    anomalies = errors + warnings
    if anomalies:
        report.extend(
            f"- [{level}] {url} — {detail}"
            for url, level, detail in anomalies
        )
    else:
        report.append("- Nessuna anomalia tecnica rilevata")

    REPORT_FILE.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    update_last_run(len(results), len(warnings), len(errors))

    print(f"Siti controllati: {len(results)}", flush=True)
    print(f"OK: {ok_count}", flush=True)
    print(f"Attenzione: {len(warnings)}", flush=True)
    print(f"Errori: {len(errors)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
