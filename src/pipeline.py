# -*- coding: utf-8 -*-
"""Skvoznoy konveyer: python -m src.pipeline --help.

Dvizhenie strogo odnonapravlennoe: raw -> interim -> processed.
raw nikogda ne perezapisyvaetsya.
"""
import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd

from .config import (INTERIM_DIR, LOGS_DIR, PROCESSED_DIR, RAW_MAIN_FILE,
                     SAMPLE_N_ROWS)
from .io_utils import bench_write_read, make_sample_streaming, read_raw_csv
from .cleaning import clean_frame
from .db import load_sqlite

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("pipeline")


def cmd_sample(args):
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    dst = INTERIM_DIR / "sample_200k.csv"
    n = make_sample_streaming(args.input, dst, n_rows=args.n)
    print(f"sample: {n} strok -> {dst}")


def cmd_serialize(args):
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    df = read_raw_csv(args.input, nrows=args.nrows)
    res = bench_write_read(df, INTERIM_DIR / "source")
    for k, v in res.items():
        print(f"{k}: {v['size_mb']:.1f} MB write={v['write_s']:.2f}s "
              f"read={v['read_s']:.2f}s")


def cmd_clean(args):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    df = read_raw_csv(args.input, nrows=args.nrows)
    n0 = len(df)
    df = clean_frame(df)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, compression="zstd")
    dt = time.perf_counter() - t0
    print(f"clean: {n0} -> {len(df)} ({len(df)/n0*100:.1f}%) za {dt:.1f}s -> {out}")


def cmd_load_sqlite(args):
    dt = load_sqlite(args.parquet, args.db)
    print(f"sqlite loaded za {dt:.1f}s -> {args.db}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="LR1 pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="srez 200k potokovym chteniem")
    s.add_argument("--input", default=str(RAW_MAIN_FILE))
    s.add_argument("--n", type=int, default=SAMPLE_N_ROWS)
    s.set_defaults(func=cmd_sample)
    s = sub.add_parser("serialize", help="sravnit formaty")
    s.add_argument("--input", default=str(RAW_MAIN_FILE))
    s.add_argument("--nrows", type=int, default=None)
    s.set_defaults(func=cmd_serialize)
    s = sub.add_parser("clean", help="ochistka -> processed/clean.parquet")
    s.add_argument("--input", default=str(RAW_MAIN_FILE))
    s.add_argument("--output",
                   default=str(PROCESSED_DIR / "clean.parquet"))
    s.add_argument("--nrows", type=int, default=None)
    s.set_defaults(func=cmd_clean)
    s = sub.add_parser("load-sqlite", help="zagruzit v SQLite (3NF)")
    s.add_argument("--parquet",
                   default=str(PROCESSED_DIR / "clean.parquet"))
    s.add_argument("--db",
                   default=str(PROCESSED_DIR / "dataset.db"))
    s.set_defaults(func=cmd_load_sqlite)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
