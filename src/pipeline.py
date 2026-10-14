# -*- coding: utf-8 -*-
"""Сквозной конвейер (шаг 13): одна команда вместо ручных ячеек блокнота.

Движение строго в одну сторону: raw -> interim -> processed.
Исходники в raw никогда не перезаписываются.
"""
import argparse  # параметры командной строки (--input, --output...)
import logging
import sys
import time
from pathlib import Path

import pandas as pd  # здесь напрямую не используется, но нужен окружению

from .config import INTERIM_DIR, LOGS_DIR, PROCESSED_DIR, RAW_MAIN_FILE, SAMPLE_N_ROWS
from .io_utils import bench_write_read, make_sample_streaming, read_raw_csv
from .cleaning import clean_frame  # вся логика очистки — там, здесь только вызовы
from .db import load_sqlite

# Настраиваем журнал: время, уровень, текст — и на экран, и (позже) в файл.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("pipeline")


def cmd_sample(args):
    """Команда sample: сделать срез 200k потоковым чтением."""
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    dst = INTERIM_DIR / "sample_200k.csv"
    n = make_sample_streaming(args.input, dst, n_rows=args.n)
    print(f"срез: {n} строк -> {dst}")


def cmd_serialize(args):
    """Команда serialize: сравнить форматы хранения (шаг 9)."""
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    df = read_raw_csv(args.input, nrows=args.nrows)  # читаем (можно часть)
    res = bench_write_read(df, INTERIM_DIR / "source")  # меряем форматы
    for k, v in res.items():  # печатаем итог по каждому формату
        print(f"{k}: {v['size_mb']:.1f} MB write={v['write_s']:.2f}s read={v['read_s']:.2f}s")


def cmd_clean(args):
    """Команда clean: прогнать очистку и сохранить clean.parquet."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    df = read_raw_csv(args.input, nrows=args.nrows)
    n0 = len(df)  # запомнили, сколько было
    df = clean_frame(df)  # вся очистка — один вызов
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, compression="zstd")  # колоночный формат + сжатие
    dt = time.perf_counter() - t0
    print(f"очистка: {n0} -> {len(df)} ({len(df) / n0 * 100:.1f}%) за {dt:.1f}с -> {out}")


def cmd_load_sqlite(args):
    """Команда load-sqlite: залить очищенное в SQLite (схема 3НФ)."""
    dt = load_sqlite(args.parquet, args.db)
    print(f"SQLite готов за {dt:.1f}с -> {args.db}")


def main(argv=None):
    """Разобрать команду и вызвать нужную функцию (точка входа модуля)."""
    ap = argparse.ArgumentParser(description="LR1 pipeline")  # описание для --help
    sub = ap.add_subparsers(dest="cmd", required=True)  # подкоманды обязательны
    # Дальше 4 однотипных блока: имя команды, её параметры, её функция.
    s = sub.add_parser("sample", help="срез 200k потоковым чтением")
    s.add_argument("--input", default=str(RAW_MAIN_FILE))  # какой файл резать
    s.add_argument("--n", type=int, default=SAMPLE_N_ROWS)  # сколько строк взять
    s.set_defaults(func=cmd_sample)  # какая функция выполнится
    s = sub.add_parser("serialize", help="сравнить форматы")
    s.add_argument("--input", default=str(RAW_MAIN_FILE))
    s.add_argument("--nrows", type=int, default=None)  # None = весь файл
    s.set_defaults(func=cmd_serialize)
    s = sub.add_parser("clean", help="очистка -> processed/clean.parquet")
    s.add_argument("--input", default=str(RAW_MAIN_FILE))
    s.add_argument("--output", default=str(PROCESSED_DIR / "clean.parquet"))
    s.add_argument("--nrows", type=int, default=None)
    s.set_defaults(func=cmd_clean)
    s = sub.add_parser("load-sqlite", help="загрузить в SQLite (3НФ)")
    s.add_argument("--parquet", default=str(PROCESSED_DIR / "clean.parquet"))
    s.add_argument("--db", default=str(PROCESSED_DIR / "dataset.db"))
    s.set_defaults(func=cmd_load_sqlite)
    args = ap.parse_args(argv)  # разобрать аргументы командной строки
    args.func(args)  # вызвать выбранную функцию с этими аргументами


if __name__ == "__main__":
    # Этот блок работает только при запуске файлом (python pipeline.py),
    # при импорте (python -m src.pipeline) выполняется main() из пакета.
    main()
