#!/usr/bin/env python3
"""Build Porto's parking datasets: public CC0 inventory plus an ESTIMATED parking pressure index.

Python 3.10+, standard library only. Run from any directory:
    python3 scripts/build_data.py [--output-dir DIR] [--cache-dir DIR] [--offline]

Writes content-hashed dataset files and a small manifest.json into the output
directory. The pressure index is a relative estimate, never occupancy or
availability. Nothing is replaced unless every source verified and built.
"""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from porto_data.common import DataError, Fetcher, utc_now  # noqa: E402
from porto_data.inventory import build_inventory  # noqa: E402
from porto_data.pressure import build_pressure  # noqa: E402
from porto_data.publish import publish  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "public/data"
DEFAULT_CACHE_DIR = ROOT / ".cache/porto-data"


def build(output_dir, cache_dir, offline):
    fetcher = Fetcher(cache_dir=cache_dir, offline=offline)
    collections, attributes, inventory_sources = build_inventory(fetcher)
    pressure, pressure_sources = build_pressure(fetcher, collections)
    return publish(
        output_dir, generated_at=utc_now(), collections=collections, attributes=attributes,
        pressure=pressure, sources=inventory_sources + pressure_sources,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="Directory for manifest and dataset files (default: public/data)")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR,
                        help="Raw response cache (default: .cache/porto-data)")
    parser.add_argument("--offline", action="store_true",
                        help="Use only cached raw responses; fail on a cache miss")
    args = parser.parse_args(argv)
    try:
        manifest = build(args.output_dir, args.cache_dir, args.offline)
    except (DataError, OSError, ValueError) as exc:
        print(f"Porto data build failed; previous data was not replaced: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output_dir / 'manifest.json'} (generated {manifest['generatedAt']})")
    for name, info in manifest["datasets"].items():
        count = info.get("featureCount", info.get("cellCount"))
        print(f"  {name}: {count} records, {info['bytes']} bytes -> {info['path']}")
    print("Inventory/tariffs plus an estimated pressure index; not live availability or occupancy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
