from __future__ import annotations

import csv
import sys
from pathlib import Path

from packages.common.config import get_settings, require_uid_hmac_secret
from packages.common.uid import hash_uid, normalize_uid

# Сырые коды зачисленных (приватные, из приказов) → HMAC-метки для калибровки.
# Namespace должен совпадать с парсером вуза (см. packages/parsers/<code>.py).
NAMESPACES = {
    "itmo": "itmo:2026:portal-code:v1",
}


def hash_labels(source_csv: Path, output_csv: Path, *, namespace: str, secret: str) -> int:
    with source_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["university", "order", "applicant_uid_hmac", "enrolled"]
        )
        writer.writeheader()
        for row in rows:
            uid = normalize_uid(row["uid_code"])
            writer.writerow(
                {
                    "university": row["university"],
                    "order": row["order"],
                    "applicant_uid_hmac": hash_uid(
                        secret=secret, identity_namespace=namespace, uid=uid
                    ),
                    "enrolled": "1",
                }
            )
    return len(rows)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m apps.tools.hash_labels <university_code>")
    code = sys.argv[1]
    namespace = NAMESPACES.get(code)
    if namespace is None:
        raise SystemExit(f"unknown university code: {code}")
    settings = get_settings()
    secret = require_uid_hmac_secret(settings)
    source = Path("fixtures/private") / f"orders_{code}_2026.csv"
    output = Path("fixtures/private") / f"orders_{code}_2026_hmac.csv"
    if not source.is_file():
        raise SystemExit(f"labels file not found: {source}")
    count = hash_labels(source, output, namespace=namespace, secret=secret)
    print(f"hashed {count} labels → {output}")


if __name__ == "__main__":
    main()
