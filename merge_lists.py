from __future__ import annotations

import html
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

SOURCES_FILE = Path("sources.txt")
OUTPUT_FILE = Path("lista.txt")
LAST_RUN_FILE = Path("last-run.txt")
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_TIMEOUT_SECONDS = 30


def read_sources() -> list[str]:
    if not SOURCES_FILE.exists():
        raise RuntimeError("File sources.txt non trovato")

    sources: list[str] = []
    for raw_line in SOURCES_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            sources.append(line)

    if not sources:
        raise RuntimeError("Inserisci almeno un URL sorgente valido in sources.txt")

    return sources


def download_once(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
            "Accept": "text/plain,text/html;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )

    with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def download(url: str) -> str:
    last_error: Exception | None = None

    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            print(f"  Tentativo {attempt}/{DOWNLOAD_ATTEMPTS}")
            return download_once(url)
        except Exception as error:
            last_error = error
            print(
                f"  Tentativo {attempt} fallito: {error}",
                file=sys.stderr,
            )
            if attempt < DOWNLOAD_ATTEMPTS:
                time.sleep(2 ** (attempt - 1))

    raise RuntimeError(
        f"sorgente non raggiungibile dopo {DOWNLOAD_ATTEMPTS} tentativi: {last_error}"
    )


def extract_urls(content: str):
    for raw_line in content.splitlines():
        line = html.unescape(raw_line).strip()
        if not line or line.startswith("#"):
            continue

        for match in URL_PATTERN.findall(line):
            yield match.rstrip(".,;:)]}\"")


def normalize_url(value: str) -> tuple[str, str] | None:
    """Restituisce (chiave di confronto, URL da pubblicare).

    La chiave considera uguali http/https, www/non-www, slash finale,
    frammenti e percorsi dello stesso dominio. Viene mantenuto nella lista
    finale il primo URL incontrato per ciascun dominio.
    """
    try:
        parsed = urlsplit(value.strip())
        scheme = parsed.scheme.lower()
        if scheme not in {"http", "https"} or not parsed.hostname:
            return None

        hostname = parsed.hostname.lower().rstrip(".")
        port = parsed.port

        canonical_host = hostname[4:] if hostname.startswith("www.") else hostname
        key = canonical_host if not port else f"{canonical_host}:{port}"

        display_host = hostname
        if ":" in display_host and not display_host.startswith("["):
            display_host = f"[{display_host}]"

        if port and not (
            (scheme == "http" and port == 80)
            or (scheme == "https" and port == 443)
        ):
            netloc = f"{display_host}:{port}"
        else:
            netloc = display_host

        path = parsed.path
        if path == "/":
            path = ""
        elif path:
            path = path.rstrip("/")

        normalized = urlunsplit((scheme, netloc, path, parsed.query, ""))
        return key, normalized
    except (TypeError, ValueError):
        return None


def add_content_to_unique(content: str, unique: dict[str, str]) -> None:
    for candidate in extract_urls(content):
        result = normalize_url(candidate)
        if result:
            key, normalized = result
            unique.setdefault(key, normalized)


def main() -> int:
    try:
        sources = read_sources()
        unique: dict[str, str] = {}
        successful_sources = 0
        failed_sources: list[str] = []

        for source in sources:
            print(f"Scaricamento: {source}")
            try:
                content = download(source)
                add_content_to_unique(content, unique)
                successful_sources += 1
            except Exception as error:
                failed_sources.append(f"{source} — {error}")
                print(f"Avviso: {source} ignorata temporaneamente: {error}", file=sys.stderr)

        fallback_used = False
        if failed_sources and OUTPUT_FILE.exists():
            previous_content = OUTPUT_FILE.read_text(encoding="utf-8")
            add_content_to_unique(previous_content, unique)
            fallback_used = True
            print(
                "Usata la lista precedente come protezione contro perdite temporanee.",
                file=sys.stderr,
            )

        if not unique:
            raise RuntimeError("Nessun URL valido trovato nelle sorgenti")

        sorted_urls = [
            url
            for _, url in sorted(
                unique.items(),
                key=lambda item: item[0].casefold(),
            )
        ]

        OUTPUT_FILE.write_text(
            "\n".join(sorted_urls) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        status_lines = [
            f"Aggiornamento UTC: {datetime.now(timezone.utc).isoformat()}",
            f"Sorgenti configurate: {len(sources)}",
            f"Sorgenti riuscite: {successful_sources}",
            f"Sorgenti non raggiungibili: {len(failed_sources)}",
            f"Siti unici: {len(unique)}",
            "Ordinamento: alfabetico per dominio",
            f"Protezione con lista precedente: {'sì' if fallback_used else 'no'}",
        ]

        if failed_sources:
            status_lines.append("Errori temporanei:")
            status_lines.extend(f"- {failure}" for failure in failed_sources)

        LAST_RUN_FILE.write_text(
            "\n".join(status_lines) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        print(f"Sorgenti riuscite: {successful_sources}/{len(sources)}")
        print(f"Generati {len(unique)} siti unici in ordine alfabetico")
        return 0

    except Exception as error:
        print(f"Errore: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
