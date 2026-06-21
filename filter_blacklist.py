from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

BLACKLIST_FILE = Path("blacklist.txt")
AUTO_EXCLUDED_FILE = Path("auto-excluded.txt")
OUTPUT_FILE = Path("lista.txt")
LAST_RUN_FILE = Path("last-run.txt")


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


def read_domains(path: Path, required: bool = False) -> set[str]:
    if not path.exists():
        if required:
            raise RuntimeError(f"File {path.name} non trovato")
        return set()

    domains: set[str] = set()
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        domain = canonical_domain(line)
        if not domain:
            raise RuntimeError(
                f"Dominio non valido in {path.name} alla riga {line_number}: {line}"
            )

        domains.add(domain)

    return domains


def matching_blocked_domain(
    hostname: str,
    blocked_domains: set[str],
) -> str | None:
    canonical_host = hostname[4:] if hostname.startswith("www.") else hostname

    for blocked_domain in blocked_domains:
        if canonical_host == blocked_domain or canonical_host.endswith(
            f".{blocked_domain}"
        ):
            return blocked_domain

    return None


def update_last_run(
    manual_configured: int,
    automatic_configured: int,
    manual_removed: int,
    automatic_removed: int,
    final_entries: int,
    matched_manual: set[str],
    matched_automatic: set[str],
) -> None:
    if not LAST_RUN_FILE.exists():
        return

    prefixes = (
        "Domini configurati in blacklist:",
        "Domini configurati in auto-esclusione:",
        "Voci escluse dalla blacklist:",
        "Voci escluse automaticamente:",
        "Domini esclusi dalla blacklist:",
        "Domini esclusi automaticamente:",
    )
    status_lines: list[str] = []

    for line in LAST_RUN_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("Siti unici:"):
            status_lines.append(f"Siti unici: {final_entries}")
        elif not line.startswith(prefixes):
            status_lines.append(line)

    insert_at = next(
        (
            index
            for index, line in enumerate(status_lines)
            if line.startswith("Siti unici:")
        ),
        len(status_lines),
    )

    filter_status = [
        f"Domini configurati in blacklist: {manual_configured}",
        f"Domini configurati in auto-esclusione: {automatic_configured}",
        f"Voci escluse dalla blacklist: {manual_removed}",
        f"Voci escluse automaticamente: {automatic_removed}",
    ]
    if matched_manual:
        filter_status.append(
            "Domini esclusi dalla blacklist: " + ", ".join(sorted(matched_manual))
        )
    if matched_automatic:
        filter_status.append(
            "Domini esclusi automaticamente: "
            + ", ".join(sorted(matched_automatic))
        )

    status_lines[insert_at:insert_at] = filter_status

    LAST_RUN_FILE.write_text(
        "\n".join(status_lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    manual_domains = read_domains(BLACKLIST_FILE, required=True)
    automatic_domains = read_domains(AUTO_EXCLUDED_FILE)

    if not OUTPUT_FILE.exists():
        raise RuntimeError("File lista.txt non trovato")

    kept_urls: list[str] = []
    manual_removed = 0
    automatic_removed = 0
    matched_manual: set[str] = set()
    matched_automatic: set[str] = set()

    for raw_line in OUTPUT_FILE.read_text(encoding="utf-8").splitlines():
        url = raw_line.strip()
        if not url:
            continue

        try:
            parsed = urlsplit(url)
            hostname = parsed.hostname.lower().rstrip(".") if parsed.hostname else ""
        except (TypeError, ValueError):
            hostname = ""

        manual_match = matching_blocked_domain(hostname, manual_domains)
        if manual_match:
            manual_removed += 1
            matched_manual.add(manual_match)
            continue

        automatic_match = matching_blocked_domain(hostname, automatic_domains)
        if automatic_match:
            automatic_removed += 1
            matched_automatic.add(automatic_match)
            continue

        kept_urls.append(url)

    if not kept_urls:
        raise RuntimeError("I filtri eliminerebbero tutte le voci da lista.txt")

    OUTPUT_FILE.write_text(
        "\n".join(kept_urls) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    update_last_run(
        manual_configured=len(manual_domains),
        automatic_configured=len(automatic_domains),
        manual_removed=manual_removed,
        automatic_removed=automatic_removed,
        final_entries=len(kept_urls),
        matched_manual=matched_manual,
        matched_automatic=matched_automatic,
    )

    print(f"Domini in blacklist: {len(manual_domains)}", flush=True)
    print(f"Domini auto-esclusi: {len(automatic_domains)}", flush=True)
    print(f"Voci escluse manualmente: {manual_removed}", flush=True)
    print(f"Voci escluse automaticamente: {automatic_removed}", flush=True)
    print(f"Voci finali: {len(kept_urls)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
