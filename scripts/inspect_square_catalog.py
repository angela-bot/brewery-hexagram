#!/usr/bin/env python3
"""Validate configured Square variation IDs without printing credentials."""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env(ROOT / ".env")
catalog = json.loads((ROOT / "config" / "square-catalog.json").read_text())
configured = {
    variation["variationId"]: (product_key, variation_key, variation["label"])
    for product_key, product in catalog["products"].items()
    for variation_key, variation in product["variations"].items()
}

token = os.environ.get("SQUARE_ACCESS_TOKEN")
environment = os.environ.get("SQUARE_ENVIRONMENT", "sandbox").lower()
if not token:
    sys.exit("SQUARE_ACCESS_TOKEN is missing")

host = "connect.squareupsandbox.com" if environment == "sandbox" else "connect.squareup.com"
request = urllib.request.Request(
    f"https://{host}/v2/catalog/batch-retrieve",
    data=json.dumps({"object_ids": list(configured), "include_related_objects": True}).encode(),
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
except urllib.error.HTTPError as error:
    details = error.read().decode(errors="replace")
    sys.exit(f"Square returned HTTP {error.code}: {details}")

found = {obj["id"]: obj for obj in payload.get("objects", []) if obj.get("type") == "ITEM_VARIATION"}
for variation_id, (product_key, variation_key, label) in configured.items():
    obj = found.get(variation_id)
    if not obj:
        print(f"MISSING  {product_key}:{variation_key} — {label}")
        continue
    data = obj.get("item_variation_data", {})
    money = data.get("price_money")
    if money:
        price = f"{money.get('currency', 'USD')} {money.get('amount', 0) / 100:.2f}"
    else:
        price = "variable price"
    print(f"OK       {product_key}:{variation_key} — {data.get('name', label)} — {price}")

missing = set(configured) - set(found)
print(f"\nValidated {len(found)}/{len(configured)} configured variations in {environment}.")
sys.exit(1 if missing else 0)
