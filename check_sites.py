from __future__ import annotations

import json
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

LIST_FILE = Path("lista.txt")
BLACKLIST_FILE = Path("blacklist.txt")
AUTO_EXCLUDED_FILE = Path("auto-excluded.txt")
STATE_FILE = Path("site-health-state.json")
REPORT_FILE = Path("site-health.txt")
LAST_RUN_FILE = Path("last-run.txt")

TIMEOUT_SECONDS = 12
MAX_WORKERS = 8
MAX_BODY_BYTES = 131_072
AUTO_EXCLUDE_AFTER = 2

HARD_HTTP_CODES = {404, 410, 451}
SOFT_HTTP_CODES = {400, 401, 403, 405, 408, 409, 425, 429}

HARD_CONTENT_MARKERS = {
    "accesso al presente sito è stato disabilitato": "pagina di blocco rilevata",
    "attenzione sito illegale": "pagina di blocco rilevata",
    "piracy shield": "pagina di blocco rilevata",
    "website not found": "pagina 'website not found'",
    "site not found": "pagina 'site not found'",
    "domain not found": "dominio non trovato dalla piattaforma",
    "domain has expired": "dominio scaduto",
    "this domain has expired": "dominio scaduto",
    "account suspended": "account sospeso",
    "domain is for sale": "dominio parcheggiato o in vendita",
    "origin connection time-out": "errore Cloudflare 522",
    "web server is down": "server di origine non disponibile",
    "origin is unreachable": "server di origine non raggiungibile",
}

SOFT_CONTENT_MARKERS = {
    "just a moment...": "protezione anti-bot",
    "checking your browser": "verifica del browser richiesta",
    "temporarily unavailable": "pagina temporaneamente non disponibile",
    "maintenance mode": "sito in manutenzione",
}


@dataclass(frozen=True)
class CheckResult:
    url: str
    domain: str
    level: str
    detail: str


def canonical_domain(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None

    if "://" not in candidate:
        candidate = f"//{candidate}"

    try:
        parsed = urlsplit(candidate)
        if not parsed.hostname:
            return None

        hostname = parsed.hostname.lower().rstrip(".")
        return hostname[4:] if hostname.startswith("www.") else hostname
    except (TypeError, ValueError):
        return None


def read_domain_file(path: Path) -> set[str]:
    if not path.exists():
        return set()

    domains: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        domain = canonical_domain(line)
        if domain:
            domains.add(domain)

    return domains


def is_domain_listed(domain: str, listed_domains: set[str]) -> bool:
    return any(
        domain == listed or domain.endswith(f".{listed}")
        for listed in listed_domains
    )


def read_urls() -> list[str]:
    if not LIST_FILE.exists():
        raise RuntimeError("File lista.txt non trovato")

    return [
        line.strip()
        for line in LIST_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_state() -> dict[str, dict[str, object]]:
    if not STATE_FILE.exists():
        return {}

    try:
        value = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    return value if isinstance(value, dict) else {}


def ssl_error_detail(error: BaseException) -> str:
    text = str(error).casefold()
    if "certificate verify failed" in text or "self-signed certificate" in text:
        return "certificato TLS non valido (possibile pagina di blocco o configurazione errata)"
    return f"errore SSL/TLS: {error}"


def decode_body(body: bytes, charset: str | None) -> str:
    return body.decode(charset or "utf-8", errors="replace").casefold()


def find_marker(content: str, markers: dict[str, str]) -> str | None:
    for marker, detail in markers.items():
        if marker in content:
            return detail
    return None


def check_url(url: str) -> CheckResult:
    domain = canonical_domain(url) or url
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 Chrome/126 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )

    status = 0
    final_url = url
    charset: str | None = None
    body = b""

    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", 200)
            final_url = response.geturl()
            charset = response.headers.get_content_charset()
            body = response.read(MAX_BODY_BYTES)
    except HTTPError as error:
        status = error.code
        final_url = error.geturl()
        charset = error.headers.get_content_charset() if error.headers else None
        try:
            body = error.read(MAX_BODY_BYTES)
        except Exception:
            body = b""
    except ssl.SSLCertVerificationError as error:
        return CheckResult(url, domain, "ERRORE", ssl_error_detail(error))
    except (socket.timeout, TimeoutError):
        return CheckResult(
            url,
            domain,
            "ERRORE",
            f"timeout oltre {TIMEOUT_SECONDS} secondi",
        )
    except ssl.SSLError as error:
        return CheckResult(url, domain, "ERRORE", ssl_error_detail(error))
    except URLError as error:
        reason = error.reason
        if isinstance(reason, ssl.SSLError):
            detail = ssl_error_detail(reason)
        elif isinstance(reason, socket.gaierror):
            detail = f"errore DNS: {reason}"
        elif isinstance(reason, socket.timeout):
            detail = f"timeout oltre {TIMEOUT_SECONDS} secondi"
        else:
            detail = f"connessione non riuscita: {reason}"
        return CheckResult(url, domain, "ERRORE", detail)
    except Exception as error:
        return CheckResult(url, domain, "ERRORE", f"errore inatteso: {error}")

    content = decode_body(body, charset)
    compact_content = " ".join(content.split())

    if compact_content in {"error1", "error 1"}:
        return CheckResult(url, domain, "ERRORE", "pagina contenente soltanto 'error1'")

    hard_marker = find_marker(content, HARD_CONTENT_MARKERS)
    if hard_marker:
        return CheckResult(url, domain, "ERRORE", hard_marker)

    if status >= 500 or status in HARD_HTTP_CODES:
        return CheckResult(url, domain, "ERRORE", f"HTTP {status}")

    soft_marker = find_marker(content, SOFT_CONTENT_MARKERS)
    if soft_marker:
        return CheckResult(url, domain, "ATTENZIONE", soft_marker)

    if status in SOFT_HTTP_CODES or status >= 400:
        return CheckResult(url, domain, "ATTENZIONE", f"HTTP {status}")

    final_domain = canonical_domain(final_url)
    if final_domain and final_domain != domain:
        return CheckResult(
            url,
            domain,
            "ATTENZIONE",
            f"reindirizza verso {final_domain}",
        )

    if len(body) < 100:
        return CheckResult(url, domain, "ATTENZIONE", "risposta insolitamente breve")

    return CheckResult(url, domain, "OK", f"HTTP {status}")


def write_auto_excluded(domains: set[str]) -> None:
    lines = [
        "# Generato automaticamente da check_sites.py.",
        f"# Un dominio entra dopo {AUTO_EXCLUDE_AFTER} errori tecnici consecutivi.",
        "# Viene rimosso automaticamente quando torna raggiungibile.",
        "",
    ]
    lines.extend(sorted(domains))
    AUTO_EXCLUDED_FILE.write_text(
        "\n".join(lines).rstrip() + "\n",
        encoding="utf-8",
        newline="\n",
    )


def update_last_run(
    checked: int,
    skipped: int,
    warnings: int,
    errors: int,
    auto_excluded: int,
) -> None:
    if not LAST_RUN_FILE.exists():
        return

    prefixes = (
        "Siti sottoposti a controllo tecnico:",
        "Siti saltati perché in blacklist manuale:",
        "Avvisi tecnici:",
        "Errori tecnici:",
        "Domini auto-esclusi:",
        "Rapporto tecnico:",
    )
    lines = [
        line
        for line in LAST_RUN_FILE.read_text(encoding="utf-8").splitlines()
        if not line.startswith(prefixes)
    ]
    lines.extend(
        [
            f"Siti sottoposti a controllo tecnico: {checked}",
            f"Siti saltati perché in blacklist manuale: {skipped}",
            f"Avvisi tecnici: {warnings}",
            f"Errori tecnici: {errors}",
            f"Domini auto-esclusi: {auto_excluded}",
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
    manual_blacklist = read_domain_file(BLACKLIST_FILE)
    previous_state = read_state()

    urls_to_check: list[str] = []
    skipped = 0
    for url in urls:
        domain = canonical_domain(url)
        if domain and is_domain_listed(domain, manual_blacklist):
            skipped += 1
            continue
        urls_to_check.append(url)

    results: list[CheckResult] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_url, url) for url in urls_to_check]
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda result: result.domain.casefold())
    now = datetime.now(timezone.utc).isoformat()
    next_state: dict[str, dict[str, object]] = {}
    auto_excluded: set[str] = set()

    for result in results:
        previous = previous_state.get(result.domain, {})
        previous_count = previous.get("consecutive_errors", 0)
        if not isinstance(previous_count, int):
            previous_count = 0

        if result.level == "ERRORE":
            consecutive_errors = previous_count + 1
        else:
            consecutive_errors = 0

        if consecutive_errors >= AUTO_EXCLUDE_AFTER:
            auto_excluded.add(result.domain)

        next_state[result.domain] = {
            "consecutive_errors": consecutive_errors,
            "last_level": result.level,
            "last_detail": result.detail,
            "last_checked_utc": now,
        }

    STATE_FILE.write_text(
        json.dumps(next_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_auto_excluded(auto_excluded)

    warnings = [result for result in results if result.level == "ATTENZIONE"]
    errors = [result for result in results if result.level == "ERRORE"]
    ok_count = len(results) - len(warnings) - len(errors)

    report = [
        f"Controllo UTC: {now}",
        f"Siti controllati: {len(results)}",
        f"Siti saltati perché in blacklist manuale: {skipped}",
        f"OK: {ok_count}",
        f"Attenzione: {len(warnings)}",
        f"Errori: {len(errors)}",
        f"Domini auto-esclusi: {len(auto_excluded)}",
        f"Soglia auto-esclusione: {AUTO_EXCLUDE_AFTER} errori tecnici consecutivi",
        (
            "Nota: il risultato dipende dalla rete del runner GitHub e può "
            "differire da quello visibile in Italia."
        ),
        "",
        "Anomalie rilevate:",
    ]

    anomalies = errors + warnings
    if anomalies:
        report.extend(
            (
                f"- [{result.level}] {result.url} — {result.detail} "
                f"(errori consecutivi: "
                f"{next_state[result.domain]['consecutive_errors']})"
            )
            for result in anomalies
        )
    else:
        report.append("- Nessuna anomalia tecnica rilevata")

    REPORT_FILE.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    update_last_run(
        checked=len(results),
        skipped=skipped,
        warnings=len(warnings),
        errors=len(errors),
        auto_excluded=len(auto_excluded),
    )

    print(f"Siti controllati: {len(results)}", flush=True)
    print(f"Siti saltati: {skipped}", flush=True)
    print(f"OK: {ok_count}", flush=True)
    print(f"Attenzione: {len(warnings)}", flush=True)
    print(f"Errori: {len(errors)}", flush=True)
    print(f"Domini auto-esclusi: {len(auto_excluded)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
