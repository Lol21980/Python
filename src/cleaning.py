# -*- coding: utf-8 -*-
"""Очистка данных: отдельная функция на каждый этап (шаг 12).

Каждая функция принимает DataFrame и возвращает DataFrame.
Повторный запуск ничего не портит (идемпотентность).
"""
import logging
import re

import pandas as pd

from .config import COLUMN_MAP_RU_EN, DROP_COLUMNS, HIDDEN_MISSING_TOKENS, SCHEMA_OPTIMIZED

log = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")  # любые пробелы подряд (для склейки в один)
_HTML_RE = re.compile(r"<[^>]+>")  # HTML-теги (для удаления из текста)


def _counts(tag, before, after):
    """Записать в журнал, сколько строк было и стало на этапе."""
    log.info("%s: строк было %d, стало %d (дельта %+d)", tag, before, after, after - before)


def rename_columns(df):
    """Привести имена колонок к виду country_code (ru -> en, нижний регистр)."""
    before = len(df)
    # Переименовываем только те русские имена, что реально есть в таблице,
    # поэтому повторный запуск не падает (русских имён уже нет).
    df = df.rename(columns={k: v for k, v in COLUMN_MAP_RU_EN.items() if k in df.columns})
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    _counts("rename_columns", before, len(df))
    return df


def coerce_types(df):
    """Привести типы: year -> целое, value -> число. Мусор -> NaN."""
    before = len(df)
    if "year" in df.columns:
        # Int16 с большой буквы умеет хранить пропуски (обычный int — нет).
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int16")
    if "value" in df.columns:
        s = df["value"].astype("string")
        # Убираем разделители тысяч: обычный и неразрывный (\u00a0) пробелы.
        s = s.str.replace("\u00a0", "", regex=False).str.replace(" ", "", regex=False)
        # Десятичную запятую русской локали меняем на точку: "1,5" -> "1.5".
        s = s.mask(s.str.contains(",", na=False), s.str.replace(",", ".", regex=False))
        # Всё, что не разобралось (порча Excel-дат вида "июн.55"), -> NaN.
        df["value"] = pd.to_numeric(s, errors="coerce")
    _counts("coerce_types", before, len(df))
    return df


def normalize_hidden_missing(df):
    """Скрытые пропуски ('..', '-', 'нет данных'...) привести к NaN."""
    before = len(df)
    toks = {t.lower() for t in HIDDEN_MISSING_TOKENS}
    for c in df.select_dtypes(include=["object", "string"]).columns:
        if c == "value":
            continue  # числа уже обработаны выше
        s = df[c].astype("string").str.strip()  # срезаем пробелы по краям
        df[c] = s.mask(s.str.lower().isin(toks), pd.NA)  # маркеры -> NaN
        df[c] = df[c].mask(df[c].astype("string") == "", pd.NA)  # пустые -> NaN
    # Нули в value пропусками НЕ считаем: 0 бывает реальным (нулевой прирост).
    n_nan = int(df["value"].isna().sum()) if "value" in df.columns else 0
    log.info("normalize_hidden_missing: NaN в value после нормализации: %d", n_nan)
    _counts("normalize_hidden_missing", before, len(df))
    return df


def drop_footnote(df):
    """Удалить служебный столбец footnote (пуст на ~96%)."""
    before = len(df)
    for c in DROP_COLUMNS:
        if c in df.columns:
            log.info("drop_footnote: удалён '%s' (непустых было %d)", c, int(df[c].notna().sum()))
            df = df.drop(columns=[c])
    _counts("drop_footnote", before, len(df))
    return df


def drop_full_duplicates(df, subset=None):
    """Удалить полностью совпадающие строки (первое вхождение оставляем)."""
    before = len(df)
    df = df.drop_duplicates(subset=subset, keep="first")
    log.info("drop_full_duplicates: удалено %d полных дубликатов", before - len(df))
    _counts("drop_full_duplicates", before, len(df))
    return df


def drop_key_duplicates(df):
    """Удалить дубли по ключу (страна, показатель, год), оставить последнюю."""
    before = len(df)
    key = [c for c in ("country_code", "indicator_code", "year") if c in df.columns]
    if key:
        df = df.sort_values(key).drop_duplicates(subset=key, keep="last")
        log.info("drop_key_duplicates: удалено %d дублей по ключу %s", before - len(df), key)
    _counts("drop_key_duplicates", before, len(df))
    return df


def normalize_categories(df, rare_min_count=5000):
    """Почистить категории: пробелы по краям, редкие (меньше 5000) -> OTHER."""
    before = len(df)
    for c in ("region", "income_group", "indicator_topic"):
        if c not in df.columns:
            continue
        s = df[c].astype("string").str.strip()
        df[c] = s.str.replace(_WS_RE, " ", regex=True)  # двойные пробелы -> один
        vc = df[c].value_counts(dropna=False)  # частоты значений
        rare = set(vc[vc < rare_min_count].index.dropna())  # что реже порога
        if rare:
            df[c] = df[c].mask(df[c].isin(rare), "OTHER")
            log.info("normalize_categories.%s: редких -> OTHER: %s", c, sorted(map(str, rare))[:8])
    # Названия и коды не трогаем сильнее strip: иначе потеряем связь с ISO3/WDI.
    for c in ("country", "indicator_name", "indicator_def"):
        if c in df.columns:
            df[c] = df[c].astype("string").str.strip().str.replace(_WS_RE, " ", regex=True)
    _counts("normalize_categories", before, len(df))
    return df


def clean_text_field(df):
    """Почистить длинный текст indicator_def: теги, переносы, пробелы."""
    before = len(df)
    if "indicator_def" in df.columns:
        s = df["indicator_def"].astype("string")
        s = s.str.replace(_HTML_RE, "", regex=True)  # вырезать <теги>
        s = s.str.replace(r"[\r\n\t]+", " ", regex=True)  # переносы -> пробел
        s = s.str.replace(_WS_RE, " ", regex=True).str.strip()
        df["indicator_def"] = s.mask(s == "", pd.NA)
    _counts("clean_text_field", before, len(df))
    return df


def check_business_rules(df):
    """Проверить смысловые правила, нарушения только ПОМЕТИТЬ флагами."""
    before = len(df)
    # Год из будущего (>2025) — подозрительно.
    df["flag_bad_year"] = (df["year"] > 2025).fillna(False).astype(bool) if "year" in df.columns else False
    # Отрицательное население — невозможно (проверяем только counts SP.POP.TOTL*).
    bad = pd.Series(False, index=df.index)
    if {"indicator_code", "value"}.issubset(df.columns):
        is_pop = df["indicator_code"].astype("string").str.startswith("SP.POP.TOTL", na=False)
        bad = bad | (is_pop & (df["value"] < 0))
    df["flag_bad_value"] = bad.fillna(False).astype(bool)
    log.info("check_business_rules: bad_year=%d bad_value=%d",
             int(df["flag_bad_year"].sum()), int(df["flag_bad_value"].sum()))
    _counts("check_business_rules", before, len(df))
    return df


def _outliers_iqr(s, k=1.5):
    """Выбросы по правилу межквартильного размаха. Возвращает маску и границы."""
    q1, q3 = s.quantile(0.25), s.quantile(0.75)  # квартили
    iqr = q3 - q1  # межквартильный размах
    lo, hi = q1 - k * iqr, q3 + k * iqr  # границы (обычно k=1.5)
    return ((s < lo) | (s > hi)), (lo, hi)


def _outliers_sigma(s, n=3):
    """Выбросы по правилу трёх сигм. Возвращает маску и границы."""
    lo, hi = s.mean() - n * s.std(), s.mean() + n * s.std()
    return ((s < lo) | (s > hi)), (lo, hi)


def flag_outliers(df, group_col="indicator_code", value_col="value"):
    """Найти выбросы двумя способами внутри каждого показателя, пометить флагами.

    Не удаляем: распределения скошены (Китай и Индия — не выбросы, а масштаб),
    поэтому формальный IQR даёт много ложных срабатываний.
    """
    before = len(df)
    df["flag_out_iqr"] = False
    df["flag_out_sigma"] = False
    if group_col in df.columns and value_col in df.columns:
        for code, idx in df.groupby(group_col, observed=True).groups.items():
            s = df.loc[idx, value_col].dropna()  # значения одного показателя
            m1, b1 = _outliers_iqr(s)
            m2, _ = _outliers_sigma(s)
            df.loc[m1.index[m1], "flag_out_iqr"] = True  # помечаем строки IQR
            df.loc[m2.index[m2], "flag_out_sigma"] = True  # помечаем строки sigma
            if len(idx) > 1000:
                log.info("выбросы %s: n=%d iqr=%d sigma=%d границы=%s",
                         code, len(idx), int(m1.sum()), int(m2.sum()),
                         tuple(round(float(x), 2) for x in b1))
    log.info("flag_outliers: всего iqr=%d sigma=%d",
             int(df["flag_out_iqr"].sum()), int(df["flag_out_sigma"].sum()))
    _counts("flag_outliers", before, len(df))
    return df


def apply_optimized_schema(df):
    """Привести все колонки к итоговой схеме типов из config.py."""
    before = len(df)
    for col, dt in SCHEMA_OPTIMIZED.items():
        if col not in df.columns:
            continue
        if dt == "category":
            df[col] = df[col].astype("category")  # словарь + коды
        elif dt == "int16":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int16")
        elif dt == "float64":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        elif dt == "string":
            df[col] = df[col].astype("string")
    for c in [x for x in df.columns if x.startswith("flag_")]:
        df[c] = df[c].astype("bool")  # все флаги — логические
    _counts("apply_optimized_schema", before, len(df))
    return df


# Порядок этапов конвейера (выполняются строго по списку).
CLEAN_STEPS = [rename_columns, coerce_types, normalize_hidden_missing, drop_footnote,
               drop_full_duplicates, drop_key_duplicates, normalize_categories,
               clean_text_field, check_business_rules, flag_outliers, apply_optimized_schema]


def clean_frame(df):
    """Прогнать таблицу через все этапы и вернуть очищенную."""
    for fn in CLEAN_STEPS:  # по очереди применяем каждую функцию
        df = fn(df)
    return df


def concat_sources(frames):
    """Склеить однотипные части (файлы) вертикально, вниз друг под друга."""
    res = pd.concat(frames, ignore_index=True)  # ignore_index — перенумеровать строки
    log.info("concat_sources: частей %d, строк стало %d", len(frames), len(res))
    return res
