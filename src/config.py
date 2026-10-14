# -*- coding: utf-8 -*-
"""Настройки проекта: пути, схема типов, параметры."""
from pathlib import Path

# Корень проекта (папка lab1): от файла src/config.py два шага вверх.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Исходники лежат отдельно и никогда не изменяются (только чтение).
RAW_EXTERNAL_DIR = Path(r"C:\Users\artur\Desktop\датасеты\Земский\csv")
RAW_MAIN_FILE = RAW_EXTERNAL_DIR / "1_датасет_население_возраст_и_пол.csv"
RAW_FILE_2 = RAW_EXTERNAL_DIR / "2_датасет_рождаемость_смертность_урбанизация.csv"
RAW_FILE_3 = RAW_EXTERNAL_DIR / "3_датасет_миграция_фертильность_брачность.csv"

# Папки проекта: движение данных только raw -> interim -> processed.
RAW_DIR = PROJECT_ROOT / "data" / "raw"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
LOGS_DIR = PROJECT_ROOT / "logs"
DOCS_DIR = PROJECT_ROOT / "docs"

CSV_ENCODING = "utf-8-sig"  # UTF-8 с BOM (так сохраняет Excel)
CSV_SEP = ";"  # разделитель русской локали Excel

# Переименование русских колонок в английский snake_case.
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

# Целевая схема типов (выбор по смыслу данных, а не по текущей выборке):
# year int16 — годы 1960-2024 с запасом влезают в диапазон ±32767;
# value float64 — население до миллиардов, float32 столько точно не хранит;
# повторяющиеся тексты -> category (словарь + коды вместо строк);
# длинное описание -> string; footnote почти пустое -> удаляем.
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

DROP_COLUMNS = ["footnote"]  # сноска пуста на ~96% — удаляем целиком

# Скрытые пропуски в тексте: всё это считаем отсутствием значения.
HIDDEN_MISSING_TOKENS = {"", "..", "-", "—", "–", "нет данных", "NA", "n/a",
                         "null", "NULL", "None", "#N/A", "?", "*", ".", ","}

SAMPLE_N_ROWS = 200_000  # размер отладочного среза (шаг 6)
RANDOM_STATE = 42  # зерно для повторяемости случайных операций
