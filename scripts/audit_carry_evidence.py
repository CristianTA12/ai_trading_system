"""Bounded archive-metadata probes for the fixed 2022 carry contract; no prices."""

import argparse
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from xml.etree import ElementTree

import requests

BUCKET = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
LIMIT = 1_000_000


def probes(snapshots=False):
    if snapshots:
        return {
            "fees_20211127": (
                "html",
                "https://web.archive.org/web/20211127151713id_/https://www.binance.com/en/fee/futureFee",
            ),
            "margin_20211223": (
                "html",
                "https://web.archive.org/web/20211223052201id_/https://www.binance.com/en/futures/trading-rules/perpetual/leverage-margin",
            ),
            "margin_20220305": (
                "html",
                "https://web.archive.org/web/20220305150219id_/https://www.binance.com/en/futures/trading-rules/perpetual/leverage-margin",
            ),
        }
    result = {}
    for kind in ("bookTicker", "bookDepth", "trades"):
        prefix = f"data/futures/um/daily/{kind}/BTCUSDT_220325/"
        result[f"future_{kind}"] = (
            "s3",
            BUCKET
            + "?"
            + urlencode(
                {
                    "prefix": prefix,
                    "max-keys": 1000,
                }
            ),
        )
    result["spot_bookTicker_day"] = (
        "s3",
        BUCKET
        + "?"
        + urlencode(
            {
                "prefix": "data/spot/daily/bookTicker/BTCUSDT/BTCUSDT-bookTicker-2022-01-03",
                "max-keys": 1000,
            }
        ),
    )
    for name, url in {
        "quarterly_rules": "www.binance.com/en/support/faq/3ae441db4ae740e19af3fe9228eb6619",
        "futures_fees": "www.binance.com/en/fee/futureFee",
        "leverage_page": "www.binance.com/en/futures/trading-rules/perpetual/leverage-margin",
    }.items():
        result[f"wayback_{name}"] = (
            "cdx",
            "https://web.archive.org/cdx/search/cdx?"
            + urlencode(
                {
                    "url": url,
                    "from": "20210101",
                    "to": "20220325",
                    "output": "json",
                    "filter": "statuscode:200",
                    "collapse": "digest",
                    "limit": 100,
                }
            ),
        )
    return result


def run(output, snapshots=False):
    output.mkdir(parents=True, exist_ok=False)

    def fetch(item):
        name, (kind, url) = item
        record = {"name": name, "kind": kind, "url": url, "requested_at_ns": time.time_ns()}
        started = time.monotonic_ns()
        try:
            with requests.get(url, timeout=20, stream=True, allow_redirects=False) as response:
                record["status"] = response.status_code
                record["headers"] = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() in {"location", "memento-datetime", "content-type", "date"}
                }
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > LIMIT:
                        raise ValueError("Response exceeds bound")
                    chunks.append(chunk)
                body = b"".join(chunks)
            (output / f"{name}.bin").write_bytes(body)
            record.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            if record["status"] == 200 and kind == "s3":
                root = ElementTree.fromstring(body)
                keys = [
                    node.findtext("s:Key", namespaces=NS) for node in root.findall("s:Contents", NS)
                ]
                record.update(
                    key_count=len(keys),
                    truncated=root.findtext("s:IsTruncated", namespaces=NS),
                    first_key=keys[0] if keys else None,
                    last_key=keys[-1] if keys else None,
                )
            elif record["status"] == 200 and kind == "cdx":
                payload = json.loads(body)
                record["snapshot_count"] = max(0, len(payload) - 1)
        except (requests.RequestException, ValueError, ElementTree.ParseError) as error:
            record["error"] = str(error)
        record["received_at_ns"] = time.time_ns()
        record["elapsed_monotonic_ns"] = time.monotonic_ns() - started
        record["wall_clock_went_backwards"] = record["received_at_ns"] < record["requested_at_ns"]
        print(json.dumps(record), flush=True)
        return record

    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(fetch, probes(snapshots).items()))
    report = {
        "probes": records,
        "requests": len(records),
        "price_archives_downloaded": 0,
        "backtests": 0,
        "models_trained": 0,
        "reserved_test_read": False,
        "empty_prefix_means": "No keys under this exact prefix; not proof of global absence",
        "http_error_means": "Access failure, not absence of historical snapshots",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "manifest.json").write_text(
        json.dumps(
            {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(output.iterdir())
                if p.is_file()
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--snapshots", action="store_true")
    args = parser.parse_args()
    run(args.output, args.snapshots)
