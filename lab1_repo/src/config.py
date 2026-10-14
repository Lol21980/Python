# -*- coding: utf-8 -*-
"""Konfiguratsiya proekta LR1: puti, skhema, parametry."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Ishodniki (vneshnyaya papka s CSV, ne izmenyaetsya)
RAW_EXTERNAL_DIR = Path(r"C:\Users\artur\Desktop\датасеты\Земский\csv")
RAW_MAIN_FILE = RAW_EXTERNAL_DIR / "1_датасет_население_возраст_и_пол.csv"
RAW_FILE_2 = RAW_EXTERNAL_DIR / "2_датасет_рождаемость_смертность_урбанизация.csv"
RAW_FILE_3 = RAW_EXTERNAL_DIR / "3_датасет_миграция_фертильность_брачность.csv"

# Vnutrennie katalogi proekta
RAW_DIR = PROJECT_ROOT / "data" / "raw"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
LOGS_DIR = PROJECT_ROOT / "logs"
DOCS_DIR = PROJECT_ROOT / "docs"

CSV_ENCODING = "utf-8-sig"
CSV_SEP = ";"

# Pereimenovanie russkikh kolonok v snake_case
COLUMN_MAP_RU_EN = {
    "Страна": "country",
    "Код страны": "country_code",
    "Регион": "region",
    "Группа дохода": "income_group",
    "Код показателя": "indicator_code",
    "Название показателя": "indicator_name",
    "Тема показателя": "indicator_topic",
    "Определение показателя": "indicator_def",
    "Год": "year",
    "Значение": "value",
    "Сноска": "footnote",
}

# Tselevaya (optimizirovannaya) skhema: vybor obosnovan predmetnoy oblastyu,
# a ne tekushchey vyborkoy.
#  - year int16: diapazon 1960-2025 << 32767
#  - value float64: naselenie do ~1.4e9, denezhnye/exponenty do 1e13;
#    float32 teryaet tselochislenuyu tochnost > 16.7 mln -> berem float64
#  - povtoryayushchiesya teksty -> category (slovar + int-kody)
#  - svobodnyy dlinnyy tekst (opredelenie) -> string[pyarrow]
#  - footnote: 90-96% pustykh -> udalyaetsya pri ochistke
SCHEMA_OPTIMIZED = {
    "country": "category",
    "country_code": "category",
    "region": "category",
    "income_group": "category",
    "indicator_code": "category",
    "indicator_name": "category",
    "indicator_topic": "category",
    "indicator_def": "string",
    "year": "int16",
    "value": "float64",
}

CATEGORY_COLUMNS = [
    "country", "country_code", "region", "income_group",
    "indicator_code", "indicator_name", "indicator_topic",
]

DROP_COLUMNS = ["footnote"]

# Skrytye propuski / musor v value (posle strip)
HIDDEN_MISSING_TOKENS = {"", "..", "-", "—", "–", "нет данных", "NA", "n/a",
                         "null", "NULL", "None", "#N/A", "?", "*", ".", ","}

SAMPLE_N_ROWS = 200_000
RANDOM_STATE = 42
