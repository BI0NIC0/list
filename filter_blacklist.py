from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

BLACKLIST_FILE = Path("blacklist.txt")
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


def read_blacklist() -> set[str]:
    if not BLACKLIST_FILE.exists():
        raise RuntimeError("File blacklist.txt non trovato")

    domains: set[str] = set()
    for line_number, raw_line in enumerate(
        BLACKLIST_FILE.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        domain = canonical_domain(line)
        if not domain:
            raise RuntimeError(
                f"Dominio non valido in blacklist.txt alla riga {line_number}: {line}"
            )

        domains.add(domain)

    return domains


def matching_blocked_domain(hostname: str, blocked_domains: set[str]) -> str | None:
    canonical_host = hostname[4:] if hostname.startswith("www.") else hostname

    for blocked_domain in blocked_domains:
        if canonical_host == blocked_domain or canonical_host.endswith(
            f".{blocked_domain}"
        ):
            return blocked_domain

    return None


def update_last_run(
    configured_domains: int,
    removed_entries: int,
    final_entries: int,
    matched_domains: set[str],
) -> None:
    if not LAST_RUN_FILE.exists():
        return

    original_lines = LAST_RUN_FILE.read_text(encoding="utf-8").splitlines()
    status_lines: list[str] = []

    for line in original_lines:
        if line.startswith("Siti unici:"):
            status_lines.append(f"Siti unici: {final_entries}")
        elif not line.startswith(
            (
                "Domini configurati in blacklist:",
                "Voci escluse dalla blacklist:",
                "Domini esclusi dalla blacklist:",
            )
        ):
            status_lines.append(line)

    insert_at = next(
        (
            index
            for index, line in enumerate(status_lines)
            if line.startswith("Siti unici:")
        ),
        len(status_lines),
    )

    blacklist_status = [
        f"Domini configurati in blacklist: {configured_domains}",
        f"Voci escluse dalla blacklist: {removed_entries}",
    ]
    if matched_domains:
        blacklist_status.append(
            "Domini esclusi dalla blacklist: " + ", ".join(sorted(matched_domains))
        )

    status_lines[insert_at:insert_at] = blacklist_status

    LAST_RUN_FILE.write_text(
        "\n".join(status_lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    blocked_domains = read_blacklist()

    if not OUTPUT_FILE.exists():
        raise RuntimeError("File lista.txt non trovato")

    kept_urls: list[str] = []
    removed_entries = 0
    matched_domains: set[str] = set()

    for raw_line in OUTPUT_FILE.read_text(encoding="utf-8").splitlines():
        url = raw_line.strip()
        if not url:
            continue

        try:
            parsed = urlsplit(url)
            hostname = parsed.hostname.lower().rstrip(".") if parsed.hostname else ""
        except (TypeError, ValueError):
            hostname = ""

        blocked_domain = matching_blocked_domain(hostname, blocked_domains)
        if blocked_domain:
            removed_entries += 1
            matched_domains.add(blocked_domain)
            continue

        kept_urls.append(url)

    if not kept_urls:
        raise RuntimeError("La blacklist eliminerebbe tutte le voci da lista.txt")

    OUTPUT_FILE.write_text(
        "\n".join(kept_urls) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    update_last_run(
        configured_domains=len(blocked_domains),
        removed_entries=removed_entries,
        final_entries=len(kept_urls),
        matched_domains=matched_domains,
    )

    print(f"Domini configurati in blacklist: {len(blocked_domains)}", flush=True)
    print(f"Voci escluse dalla blacklist: {removed_entries}", flush=True)
    print(f"Voci finali: {len(kept_urls)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
