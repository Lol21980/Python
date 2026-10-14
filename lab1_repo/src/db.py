# -*- coding: utf-8 -*-
"""Zagruzka ochishchennykh dannykh v SQLite / PostgreSQL (3NF)."""
import logging
import os
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

log = logging.getLogger(__name__)


def sqlite_url(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def pg_url_from_env():
    return (f"postgresql+psycopg2://{os.getenv('PG_USER')}:"
            f"{os.getenv('PG_PASSWORD')}@{os.getenv('PG_HOST')}:"
            f"{os.getenv('PG_PORT')}/{os.getenv('PG_DB')}")


def norm_frames(df):
    """Razlozhit shirokuyu tablitsu na 3NF: countries/indicators/observations."""
    countries = (df[["country_code", "country", "region", "income_group"]]
                 .drop_duplicates().reset_index(drop=True))
    countries.insert(0, "country_id", range(1, len(countries) + 1))
    indicators = (df[["indicator_code", "indicator_name",
                      "indicator_topic", "indicator_def"]]
                  .drop_duplicates().reset_index(drop=True))
    indicators.insert(0, "indicator_id", range(1, len(indicators) + 1))
    cmap = dict(zip(countries["country_code"].astype(str),
                    countries["country_id"]))
    imap = dict(zip(indicators["indicator_code"].astype(str),
                    indicators["indicator_id"]))
    obs = pd.DataFrame({
        "country_id": df["country_code"].astype(str).map(cmap).astype("int32"),
        "indicator_id": df["indicator_code"].astype(str).map(imap).astype("int32"),
        "year": df["year"].astype("int16"),
        "value": df["value"].astype("float64"),
    })
    return countries, indicators, obs


def load_sqlite(clean_parquet, db_path, chunksize=50_000):
    """Sozdat 3NF-tablitsy v SQLite i zagruzit paketami. Vernut vremya."""
    import sqlite3
    t0 = time.perf_counter()
    df = pd.read_parquet(clean_parquet)
    countries, indicators, obs = norm_frames(df)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    eng = create_engine(sqlite_url(db_path))
    with open(Path(__file__).resolve().parent.parent / "sql" / "schema_sqlite.sql",
              encoding="utf-8") as f:
        ddl = f.read()
    raw = sqlite3.connect(db_path)
    raw.executescript(ddl)
    raw.commit()
    raw.close()
    countries.to_sql("countries", eng, if_exists="append",
                     index=False, chunksize=chunksize)
    indicators.to_sql("indicators", eng, if_exists="append",
                      index=False, chunksize=chunksize)
    obs.to_sql("observations", eng, if_exists="append",
               index=False, chunksize=chunksize)
    dt = time.perf_counter() - t0
    log.info("sqlite load: %.1fs rows obs=%d", dt, len(obs))
    return dt


def run_control_queries(engine_url):
    """Tri kontrolnykh zaprosa; vernut dict {name: (n_rows, seconds)}."""
    eng = create_engine(engine_url)
    queries = {
        "count": "SELECT COUNT(*) FROM observations",
        "agg_by_topic": (
            "SELECT i.indicator_topic, COUNT(*), AVG(o.value) "
            "FROM observations o JOIN indicators i "
            "ON o.indicator_id=i.indicator_id GROUP BY 1"),
        "range_years": (
            "SELECT COUNT(*) FROM observations WHERE year BETWEEN 2000 AND 2020"),
    }
    out = {}
    with eng.connect() as c:
        for name, q in queries.items():
            t0 = time.perf_counter()
            rows = c.execute(text(q)).fetchall()
            out[name] = (len(rows), time.perf_counter() - t0, rows[:3])
    return out
