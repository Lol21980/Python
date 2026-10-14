# -*- coding: utf-8 -*-
"""Funktsii ochistki: kazhdaya prinimaet i vozvrashchaet DataFrame.

Idempotentnost: povtornyy zapusk na ochishchennykh dannykh nichego ne portit.
Vse resheniya logiruyutsya (bylo/stalo).
"""
import logging
import re

import numpy as np
import pandas as pd

from .config import (CATEGORY_COLUMNS, COLUMN_MAP_RU_EN, DROP_COLUMNS,
                     HIDDEN_MISSING_TOKENS, SCHEMA_OPTIMIZED)

log = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")
_HTML_RE = re.compile(r"<[^>]+>")


def _counts(tag, before, after):
    log.info("%s: strok bylo %d, stalo %d (delta %+d)",
             tag, before, after, after - before)


def rename_columns(df):
    """Privesti imena k snake_case (ru->en); uzhe pereimenovannye ne trogat."""
    before = len(df)
    df = df.rename(columns={k: v for k, v in COLUMN_MAP_RU_EN.items()
                            if k in df.columns})
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    _counts("rename_columns", before, len(df))
    return df


def coerce_types(df):
    """Yavnoe privedenie tipov: year->int16, value->float64.

    Decimal: pevodit zapyatuyu v tochku ('1,77872E+12' -> '1.77872E+12').
    Nerazobrannye -> NaN (errors='coerce').
    """
    before = len(df)
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int16")
    if "value" in df.columns:
        s = df["value"].astype("string")
        # ubrat probely-razdeliteli tysyach, zamenit desyatichnuyu zapyatuyu
        s = s.str.replace("\u00a0", "", regex=False).str.replace(" ", "", regex=False)
        # ostorozhno: zapyataya-desyatichnyy razdelitel -> tochka.
        # tysyachnye razdeliteli vida '1,036,650' ne vstrechayutsya (provereno razvedkoy),
        # poetomu zamenyaem ',' na '.' dlya vsekh nepushykh znacheniy s tsiframi.
        mask_comma = s.str.contains(",", na=False)
        s = s.mask(mask_comma, s.str.replace(",", ".", regex=False))
        df["value"] = pd.to_numeric(s, errors="coerce")
    _counts("coerce_types", before, len(df))
    return df


def normalize_hidden_missing(df):
    """Skrytye propuski ('..','-','нет данных'...) -> NaN; strip tekstov."""
    before = len(df)
    toks = {t.lower() for t in HIDDEN_MISSING_TOKENS}
    for c in df.select_dtypes(include=["object", "string"]).columns:
        if c == "value":
            continue
        s = df[c].astype("string")
        s = s.str.strip()
        df[c] = s.mask(s.str.lower().isin(toks), pd.NA)
        # pustaya stroka tozhe propusk
        df[c] = df[c].mask(df[c].astype("string") == "", pd.NA)
    # value: 0 i 9999 NE schitaem avtomaticheski propuskami (obosnovanie v otchete):
    # 0 byvaet realnym (chistaya migratsiya, prirost ~0), poetomu tolko logiruem dolyu.
    n_nan = int(df["value"].isna().sum()) if "value" in df.columns else 0
    log.info("normalize_hidden_missing: NaN v value posle normalizatsii: %d", n_nan)
    _counts("normalize_hidden_missing", before, len(df))
    return df


def drop_footnote(df):
    """Udalit sluzhebnyy stolbets footnote (~96% pustykh)."""
    before = len(df)
    for c in DROP_COLUMNS:
        if c in df.columns:
            n_notna = int(df[c].notna().sum())
            df = df.drop(columns=[c])
            log.info("drop_footnote: udalen '%s' (neпустых bylo %d)", c, n_notna)
    _counts("drop_footnote", before, len(df))
    return df


def drop_full_duplicates(df, subset=None):
    before = len(df)
    df = df.drop_duplicates(subset=subset, keep="first")
    log.info("drop_full_duplicates: udaleno %d polnykh dublikatov",
             before - len(df))
    _counts("drop_full_duplicates", before, len(df))
    return df


def drop_key_duplicates(df):
    """Dublikat po klyuchu (country_code, indicator_code, year).

    V dannykh dublikatov klyucha net (provereno), no funktsiya ostavlena
    dlya idempotentnosti konveyera i sluchaya konkatenatsii faylov.
    """
    before = len(df)
    key = [c for c in ("country_code", "indicator_code", "year") if c in df.columns]
    if key:
        df = df.sort_values(key).drop_duplicates(subset=key, keep="last")
        log.info("drop_key_duplicates: udaleno %d dubley po klyuchu %s",
                 before - len(df), key)
    _counts("drop_key_duplicates", before, len(df))
    return df


def normalize_categories(df, rare_min_count=5000):
    """Normalizatsiya kategoriy: registr, probely, slovar, redkie -> 'OTHER'.

    Primenyaetsya k region/income_group/indicator_topic.
    Spravochnye kody (country_code, indicator_code) i nazvaniya ne trogaem,
    krome strip (chtoby ne poteryat svyaz s kodami ISO3/WDI).
    """
    before = len(df)
    for c in ("region", "income_group", "indicator_topic"):
        if c not in df.columns:
            continue
        s = df[c].astype("string")
        s = s.str.strip()
        # skleit mnozhestvennye probely
        s = s.str.replace(_WS_RE, " ", regex=True)
        df[c] = s
        # redkie kategorii -> OTHER (porog po predmetnoy oblasti)
        vc = df[c].value_counts(dropna=False)
        rare = set(vc[vc < rare_min_count].index.dropna())
        if rare:
            df[c] = df[c].mask(df[c].isin(rare), "OTHER")
            log.info("normalize_categories.%s: %d redkikh -> OTHER %s",
                     c, len(rare), sorted(map(str, rare))[:8])
    # country/indicator_name: tolko strip + skleyka probelov (bez registra/kodov)
    for c in ("country", "indicator_name", "indicator_def"):
        if c in df.columns:
            s = df[c].astype("string").str.strip()
            df[c] = s.str.replace(_WS_RE, " ", regex=True)
    _counts("normalize_categories", before, len(df))
    return df


def clean_text_field(df):
    """Ochistka dlinnogo teksta indicator_def: html, perevody strok, probely."""
    before = len(df)
    if "indicator_def" in df.columns:
        s = df["indicator_def"].astype("string")
        s = s.str.replace(_HTML_RE, "", regex=True)
        s = s.str.replace(r"[\r\n\t]+", " ", regex=True)
        s = s.str.replace(_WS_RE, " ", regex=True).str.strip()
        df["indicator_def"] = s.mask(s == "", pd.NA)
    _counts("clean_text_field", before, len(df))
    return df


def check_business_rules(df):
    """Proverka predmetnykh ogranicheniy (ne udalyaem, a pomechaem flagami).

    - year v budushchem (>2025) -> flag bad_year
    - otritsatelnoe naselenie dlya SP.POP.TOTL* -> flag bad_value
    Flagi ostavlyayutsya v tablice dlya analiza (analitik reshaet sam).
    """
    before = len(df)
    df["flag_bad_year"] = (df["year"] > 2025).fillna(False).astype(bool) \
        if "year" in df.columns else False
    bad = pd.Series(False, index=df.index)
    if {"indicator_code", "value"}.issubset(df.columns):
        is_pop = df["indicator_code"].astype("string").str.startswith(
            "SP.POP.TOTL", na=False)
        bad = bad | (is_pop & (df["value"] < 0))
    df["flag_bad_value"] = bad.fillna(False).astype(bool)
    log.info("check_business_rules: bad_year=%d bad_value=%d",
             int(df["flag_bad_year"].sum()), int(df["flag_bad_value"].sum()))
    _counts("check_business_rules", before, len(df))
    return df


def detect_outliers_iqr(s, k=1.5):
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - k * iqr, q3 + k * iqr
    return (s < lo) | (s > hi), (lo, hi)


def detect_outliers_sigma(s, n=3):
    mu, sd = s.mean(), s.std()
    lo, hi = mu - n * sd, mu + n * sd
    return ((s < lo) | (s > hi)), (lo, hi)


def flag_outliers(df, group_col="indicator_code", value_col="value"):
    """Vybrosy dvumya sposobami vnutri kazhdogo pokazatelya (ne udalyaem).

    Stavim flagi flag_out_iqr / flag_out_sigma + logiruem sopostavlenie.
    Sposob vybran soznatelno: raspredeleniya silno skosheny (naselenie
    ot tysyach do milliardov), poetomu IQR na skoshennykh daet mnogo
    lozhnykh 'vybrosov' - ikh nelzya udalyat, tolko pomechat.
    """
    before = len(df)
    df["flag_out_iqr"] = False
    df["flag_out_sigma"] = False
    if group_col in df.columns and value_col in df.columns:
        for code, idx in df.groupby(group_col, observed=True).groups.items():
            s = df.loc[idx, value_col]
            m1, b1 = detect_outliers_iqr(s.dropna())
            m2, b2 = detect_outliers_sigma(s.dropna())
            df.loc[m1.index[m1], "flag_out_iqr"] = True
            df.loc[m2.index[m2], "flag_out_sigma"] = True
            if len(idx) > 1000:
                log.info("outliers %s: n=%d iqr=%d sigma=%d bounds_iqr=%s",
                         code, len(idx), int(m1.sum()), int(m2.sum()),
                         tuple(round(float(x), 2) for x in b1))
    log.info("flag_outliers: iqr=%d sigma=%d",
             int(df["flag_out_iqr"].sum()), int(df["flag_out_sigma"].sum()))
    _counts("flag_outliers", before, len(df))
    return df


def apply_optimized_schema(df):
    """Privesti k optimizirovannoy skheme (config.SCHEMA_OPTIMIZED)."""
    before = len(df)
    for col, dt in SCHEMA_OPTIMIZED.items():
        if col not in df.columns:
            continue
        if dt == "category":
            df[col] = df[col].astype("category")
        elif dt == "int16":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int16")
        elif dt == "float64":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        elif dt == "string":
            df[col] = df[col].astype("string")
    # flagi -> bool
    for c in [x for x in df.columns if x.startswith("flag_")]:
        df[c] = df[c].astype("bool")
    _counts("apply_optimized_schema", before, len(df))
    return df


CLEAN_STEPS = [
    rename_columns,
    coerce_types,
    normalize_hidden_missing,
    drop_footnote,
    drop_full_duplicates,
    drop_key_duplicates,
    normalize_categories,
    clean_text_field,
    check_business_rules,
    flag_outliers,
    apply_optimized_schema,
]


def clean_frame(df):
    """Progнат df cherez vse shagi; vernut ochishchennyy df."""
    for fn in CLEAN_STEPS:
        df = fn(df)
    return df


def concat_sources(frames):
    """Konkatenatsiya odnotipnykh chastey + kontrol styka."""
    before = sum(len(f) for f in frames)
    res = pd.concat(frames, ignore_index=True)
    log.info("concat_sources: chastey %d, strok bylo %d, stalo %d",
             len(frames), before, len(res))
    return res
