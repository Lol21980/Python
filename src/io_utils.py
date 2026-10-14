# -*- coding: utf-8 -*-
"""Ввод-вывод: чтение CSV, потоковый срез, замеры форматов (шаги 6 и 9)."""
import csv  # построчное чтение (срез без загрузки всего файла в память)
import logging
import time  # точные часы для замеров
from pathlib import Path
from statistics import median  # медиана устойчивее среднего к выбросам

import pandas as pd

from .config import CSV_ENCODING, CSV_SEP  # константы из единого конфига

log = logging.getLogger(__name__)


def read_raw_csv(path, dtype=None, nrows=None, **kw):
    """Прочитать исходный CSV. nrows ограничивает число строк (для среза)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"файл не найден: {path}")
    # low_memory=False — угадать типы одним проходом, без предупреждений.
    return pd.read_csv(path, sep=CSV_SEP, encoding=CSV_ENCODING,
                       dtype=dtype, nrows=nrows, low_memory=False, **kw)


def make_sample_streaming(src, dst, n_rows=200_000, max_scan=None):
    """Срез первых n_rows строк построчно (файл целиком в память не грузим)."""
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)  # создать папку, если нет
    kept = 0
    # Открываем сразу два файла: чтение исходника и запись среза.
    with open(src, "r", encoding=CSV_ENCODING, newline="") as fin, \
            open(dst, "w", encoding="utf-8", newline="") as fout:
        reader = csv.reader(fin, delimiter=CSV_SEP)
        writer = csv.writer(fout, delimiter=CSV_SEP)
        writer.writerow(next(reader))  # заголовок — первой строкой
        for i, row in enumerate(reader):
            if max_scan is not None and i >= max_scan:
                break  # отладочный предел сканирования
            if kept >= n_rows:
                break  # набрали нужное число строк
            writer.writerow(row)
            kept += 1
    log.info("срез: %s -> %s (%d строк)", src.name, dst.name, kept)
    return kept


def _timeit(fn, repeat=3):
    """Запустить fn repeat раз, вернуть медиану времени (первый греет кэш)."""
    ts = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return median(ts)


def bench_write_read(df, base_path, repeat=3):
    """Сравнить pickle/feather/parquet: объём, запись, чтение. Возвращает dict."""
    base_path = Path(base_path)
    base_path.parent.mkdir(parents=True, exist_ok=True)
    out = {}
    # Для каждого формата: куда писать, как писать, как читать.
    jobs = {
        "pickle": (base_path.with_suffix(".pkl"),
                   lambda p: df.to_pickle(p), lambda p: pd.read_pickle(p)),
        "feather": (base_path.with_suffix(".feather"),
                    lambda p: df.to_feather(p), lambda p: pd.read_feather(p)),
        "parquet_snappy": (base_path.with_name(base_path.stem + "_snappy.parquet"),
                           lambda p: df.to_parquet(p, compression="snappy"),
                           lambda p: pd.read_parquet(p)),
        "parquet_zstd": (base_path.with_name(base_path.stem + "_zstd.parquet"),
                         lambda p: df.to_parquet(p, compression="zstd"),
                         lambda p: pd.read_parquet(p)),
    }
    for name, (p, wf, rf) in jobs.items():
        w = _timeit(lambda: wf(p), repeat)  # время записи
        r = _timeit(lambda: rf(p), repeat)  # время чтения
        size_mb = p.stat().st_size / 1024 ** 2  # размер файла в МБ
        out[name] = {"size_mb": size_mb, "write_s": w, "read_s": r,
                     "path": str(p)}
        log.info("%s: %.1f MB write=%.2fs read=%.2fs", name, size_mb, w, r)
    return out
