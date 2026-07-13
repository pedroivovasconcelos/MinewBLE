"""Fail safely on tracked secret containers and high-confidence PII.

Only file paths and rule identifiers are printed; matched values never leave the runner.
"""
from __future__ import annotations
import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path.cwd()
MAX_TEXT_BYTES = 2_000_000
TEXT_SUFFIXES = {
    ".c", ".cpp", ".cs", ".css", ".csv", ".env", ".go", ".h", ".html",
    ".java", ".js", ".json", ".jsx", ".md", ".mjs", ".py", ".rs", ".sql",
    ".toml", ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}
RISKY_SUFFIXES = {".bak", ".bundle", ".dump", ".jks", ".key", ".keystore", ".p12", ".pem", ".pfx"}
SAFE_ENV_NAMES = {".env.example", ".env.sample", ".env.template"}
SYNTHETIC_EMAIL_DOMAINS = {"example.com", "example.invalid", "example.org", "test.invalid"}
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b")
CPF_RE = re.compile(r"(?<!\d)(\d{3})[.\s-]?(\d{3})[.\s-]?(\d{3})[-\s]?(\d{2})(?!\d)")
PHONE_RE = re.compile(
    r"(?<!\d)(?:(?:\+?55[\s.-]+\(?[1-9]{2}\)?)|(?:\([1-9]{2}\)))[\s.-]+9?\d{4}[\s.-]?\d{4}(?!\d)"
)
SENSITIVE_CONTEXT = re.compile(r"(?i)(seed|fixture|snapshot|dump|backup|bundle|credential|customer|user)")

def tracked_files() -> list[str]:
    raw = subprocess.check_output(["git", "ls-files", "-z"])
    return [item.decode("utf-8", errors="surrogateescape") for item in raw.split(b"\0") if item]

def valid_cpf(raw: str) -> bool:
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    for length in (9, 10):
        total = sum(int(digit) * weight for digit, weight in zip(digits[:length], range(length + 1, 1, -1)))
        check = (total * 10) % 11
        if check == 10:
            check = 0
        if check != int(digits[length]):
            return False
    return True

def main() -> None:
    findings: set[tuple[str, str]] = set()
    for item in tracked_files():
        posix = PurePosixPath(item)
        name = posix.name.lower()
        suffix = posix.suffix.lower()
        if name.startswith(".env") and name not in SAFE_ENV_NAMES:
            findings.add((item, "tracked-env-file"))
        if suffix in RISKY_SUFFIXES or (name.endswith((".sql.gz", ".tar.gz")) and SENSITIVE_CONTEXT.search(item)):
            findings.add((item, "risky-secret-container"))
        path = ROOT / Path(item)
        try:
            if not path.is_file() or path.stat().st_size > MAX_TEXT_BYTES:
                continue
            if suffix not in TEXT_SUFFIXES and name not in {"dockerfile", "makefile"}:
                continue
            data = path.read_bytes()
            if b"\0" in data:
                continue
            text = data.decode("utf-8", errors="ignore")
        except OSError:
            continue
        if any(valid_cpf(match.group(0)) for match in CPF_RE.finditer(text)):
            findings.add((item, "valid-cpf-pattern"))
        if PHONE_RE.search(text):
            findings.add((item, "br-phone-pattern"))
        if SENSITIVE_CONTEXT.search(item):
            for match in EMAIL_RE.finditer(text):
                if match.group(1).lower() not in SYNTHETIC_EMAIL_DOMAINS:
                    findings.add((item, "non-synthetic-email-in-sensitive-context"))
                    break
    if findings:
        print(f"Repository policy scan: FAIL ({len(findings)} redacted finding(s))")
        for path, rule in sorted(findings):
            print(f"- {path}: {rule}")
        raise SystemExit(1)
    print("Repository policy scan: PASS")

if __name__ == "__main__":
    main()
