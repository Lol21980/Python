# -*- coding: utf-8 -*-
"""Chtenie/zapis raznykh formatov + potokovyy srez."""
import csv
import logging
import time
from pathlib import Path
from statistics import median

import pandas as pd

from .config import CSV_ENCODING, CSV_SEP

log = logging.getLogger(__name__)


def read_raw_csv(path, dtype=None, nrows=None, **kw):
    """Prochitat iskhodnyy CSV (razdelitel ';', kodirovka utf-8-sig)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"fayl ne nayden: {path}")
    return pd.read_csv(
        path, sep=CSV_SEP, encoding=CSV_ENCODING,
        dtype=dtype, nrows=nrows, low_memory=False, **kw,
    )


def make_sample_streaming(src, dst, n_rows=200_000, max_scan=None):
    """Potokovyy srez pervykh n_rows stroк (bez zagruzki vsego fayla).

    Chitaet postrochno cherez csv-модуль, pishet pervye n_rows dannykh.
    Vozvrashchaet chislo zapisannykh strok.
    """
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    kept = 0
    with open(src, "r", encoding=CSV_ENCODING, newline="") as fin, \
            open(dst, "w", encoding="utf-8", newline="") as fout:
        reader = csv.reader(fin, delimiter=CSV_SEP)
        writer = csv.writer(fout, delimiter=CSV_SEP)
        header = next(reader)
        writer.writerow(header)
        for i, row in enumerate(reader):
            if max_scan is not None and i >= max_scan:
                break
            if kept < n_rows:
                writer.writerow(row)
                kept += 1
            else:
                break
    log.info("srez: %s -> %s (%d strok)", src.name, dst.name, kept)
    return kept


def bench_write_read(df, base_path, repeat=3):
    """Zamerit obyom/zapis/chtenie dlya pickle/feather/parquet.

    Vozvrashchaet dict: {format: {size_mb, write_s, read_s}} (mediana).
    """
    from pathlib import Path as _P
    base_path = _P(base_path)
    base_path.parent.mkdir(parents=True, exist_ok=True)
    out = {}

    def _timeit(fn):
        ts = []
        for _ in range(repeat):
            t0 = time.perf_counter()
            fn()
            ts.append(time.perf_counter() - t0)
        return median(ts)

    jobs = {
        "pickle": (base_path.with_suffix(".pkl"),
                   lambda p: df.to_pickle(p),
                   lambda p: pd.read_pickle(p)),
        "feather": (base_path.with_suffix(".feather"),
                    lambda p: df.to_feather(p),
                    lambda p: pd.read_feather(p)),
        "parquet_snappy": (base_path.with_name(base_path.stem + "_snappy.parquet"),
                           lambda p: df.to_parquet(p, compression="snappy"),
                           lambda p: pd.read_parquet(p)),
        "parquet_zstd": (base_path.with_name(base_path.stem + "_zstd.parquet"),
                         lambda p: df.to_parquet(p, compression="zstd"),
                         lambda p: pd.read_parquet(p)),
    }
    for name, (p, wf, rf) in jobs.items():
        w = _timeit(lambda: wf(p))
        r = _timeit(lambda: rf(p))
        size_mb = p.stat().st_size / 1024 ** 2
        out[name] = {"size_mb": size_mb, "write_s": w, "read_s": r,
                     "path": str(p)}
        log.info("%s: %.1f MB write=%.2fs read=%.2fs",
                 name, size_mb, w, r)
    return out
