# -*- coding: utf-8 -*-
"""Загрузка очищенных данных в SQLite / PostgreSQL в 3-й нормальной форме."""
import logging
import os  # переменные окружения (реквизиты Postgres из .env)
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text  # движок БД и SQL-запросы

log = logging.getLogger(__name__)


def sqlite_url(path):
    """Собрать адрес SQLite-базы (это просто файл) и создать его папку."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def pg_url_from_env():
    """Собрать адрес PostgreSQL из переменных окружения (пароля в коде нет)."""
    return (f"postgresql+psycopg2://{os.getenv('PG_USER')}:"
            f"{os.getenv('PG_PASSWORD')}@{os.getenv('PG_HOST')}:"
            f"{os.getenv('PG_PORT')}/{os.getenv('PG_DB')}")


def norm_frames(df):
    """Разложить широкую таблицу на 3 таблицы 3НФ: страны/показатели/наблюдения."""
    # Справочник стран: уникальные строки + свой id.
    countries = df[["country_code", "country", "region", "income_group"]].drop_duplicates().reset_index(drop=True)
    countries.insert(0, "country_id", range(1, len(countries) + 1))  # id с 1
    # Справочник показателей: то же самое.
    indicators = df[["indicator_code", "indicator_name", "indicator_topic", "indicator_def"]].drop_duplicates().reset_index(drop=True)
    indicators.insert(0, "indicator_id", range(1, len(indicators) + 1))
    # Словари «код -> id» для замены длинных строк на короткие ключи.
    cmap = dict(zip(countries["country_code"].astype(str), countries["country_id"]))
    imap = dict(zip(indicators["indicator_code"].astype(str), indicators["indicator_id"]))
    # Факты: только ключи + год + значение (длинных строк больше нет).
    obs = pd.DataFrame({
        "country_id": df["country_code"].astype(str).map(cmap).astype("int32"),
        "indicator_id": df["indicator_code"].astype(str).map(imap).astype("int32"),
        "year": df["year"].astype("int16"),
        "value": df["value"].astype("float64"),
    })
    return countries, indicators, obs


def load_sqlite(clean_parquet, db_path, chunksize=50_000):
    """Создать таблицы 3НФ в SQLite и загрузить всё пакетами. Вернуть секунды."""
    import sqlite3  # встроенная файловая СУБД (установки не требует)

    t0 = time.perf_counter()  # старт замера
    df = pd.read_parquet(clean_parquet)  # читаем очищенный набор
    countries, indicators, obs = norm_frames(df)  # раскладываем на 3 таблицы
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()  # старую базу удаляем, чтобы загрузка была чистой
    eng = create_engine(sqlite_url(db_path))  # движок для пакетной вставки
    # DDL схемы читаем из файла (он же создан в DBeaver через Generate SQL).
    with open(Path(__file__).resolve().parent.parent / "sql" / "schema_sqlite.sql",
              encoding="utf-8") as f:
        ddl = f.read()
    raw = sqlite3.connect(db_path)  # прямое соединение для выполнения скрипта
    raw.executescript(ddl)  # создаём таблицы и индексы одним скриптом
    raw.commit()  # фиксируем изменения
    raw.close()  # закрываем прямое соединение
    # Грузим по очереди: сначала справочники, потом факты со ссылками на них.
    countries.to_sql("countries", eng, if_exists="append", index=False, chunksize=chunksize)
    indicators.to_sql("indicators", eng, if_exists="append", index=False, chunksize=chunksize)
    obs.to_sql("observations", eng, if_exists="append", index=False, chunksize=chunksize)
    dt = time.perf_counter() - t0  # сколько секунд заняла вся загрузка
    log.info("sqlite load: %.1fс, строк observations=%d", dt, len(obs))
    return dt


def run_control_queries(engine_url):
    """Три контрольных запроса из методички. Вернуть {имя: (строки, секунды)}."""
    eng = create_engine(engine_url)
    queries = {
        "count": "SELECT COUNT(*) FROM observations",  # всего записей
        "agg_by_topic": (  # агрегат по рубрике (с соединением таблиц)
            "SELECT i.indicator_topic, COUNT(*), AVG(o.value) "
            "FROM observations o JOIN indicators i "
            "ON o.indicator_id=i.indicator_id GROUP BY 1"),
        "range_years": (  # выборка по диапазону лет (для проверки индекса)
            "SELECT COUNT(*) FROM observations WHERE year BETWEEN 2000 AND 2020"),
    }
    out = {}
    with eng.connect() as c:  # одно соединение на все запросы
        for name, q in queries.items():  # перебираем запросы
            t0 = time.perf_counter()  # старт замера
            rows = c.execute(text(q)).fetchall()  # выполнить и забрать всё
            out[name] = (len(rows), time.perf_counter() - t0, rows[:3])
    return out
