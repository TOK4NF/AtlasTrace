from __future__ import annotations

from urllib.parse import urlparse
import re


EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63}\b")
URL_RE = re.compile(r"https?://[^\s<>'\"`]+", flags=re.I)
IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-/]{6,}\d)(?!\w)")
DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\b",
    flags=re.I,
)


def extract_observables(text: str) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    results: list[dict[str, str]] = []

    def add(kind: str, value: str) -> None:
        normalized = value.strip().rstrip(").,]>}\"'")
        key = (kind, normalized.lower())
        if not normalized or key in seen:
            return
        seen.add(key)
        results.append({"kind": kind, "value": normalized})

    for email in EMAIL_RE.findall(text):
        add("email", email)
        domain = email.split("@", 1)[-1]
        add("domain", domain)

    for url in URL_RE.findall(text):
        add("url", url)
        hostname = urlparse(url).hostname
        if hostname:
            add("domain", hostname)

    for ipv4 in IPV4_RE.findall(text):
        add("ipv4", ipv4)

    for phone in PHONE_RE.findall(text):
        digits = re.sub(r"\D+", "", phone)
        if 8 <= len(digits) <= 16:
            add("phone", phone.strip())

    for domain in DOMAIN_RE.findall(text):
        if "@" not in domain:
            add("domain", domain)

    return results
