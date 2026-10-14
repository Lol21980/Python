# LR1: Obrabotka i ochistka dannykh (variant 12, WDI SP.POP)

Polnyy marshrut: okruzhenie → GitHub → zavisimosti → Colab →
Jupyter → serializatsiya → skhema → pandas/polars →
ochistka (modul + bloknot) → SQLite + PostgreSQL.

## Trebovaniya

- Python **3.12.14** (`python --version`; na mashine otcheta 3.12.10 —
  raznitsa tolko v korrektiruyushchem vypuske, sm. otchet).
- VS Code + rasshireniya: Python, Pylance, Jupyter, Ruff, GitLens.
- Git + public repo GitHub (ssylka sdana prepodavatelyu).

## Razvertyvanie

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"   # dolzhen byt vnutri .venv
pip install -r requirements.txt                 # bystryy variant
# ili strogo po metodichke (poetry):
poetry env use py -3.12
poetry config virtualenvs.in-project true
poetry install
```

Proverki iz metodichki: `python -c "import sys; print(sys.prefix != sys.base_prefix)"`
(True), vybor interpreatora v storoke sostoyaniya VS Code,
`.venv` v `.gitignore`, eksperiment s kopirovaniem papki (okruzhenie ne perenositsya).

## Zapusk konveyera

```powershell
python -m src.pipeline sample --n 200000          # srez v data/interim/sample_200k.csv
python -m src.pipeline serialize --nrows 200000   # sravnenie formatov (polnyy nabor po umolchaniyu)
python -m src.pipeline clean                      # data/processed/clean.parquet
python -m src.pipeline clean --nrows 200000       # rezhim sreza dlya otladki
python -m src.pipeline load-sqlite                # data/processed/dataset.db (3NF)
```

Bloknoty: `notebooks/01_overview.ipynb` (razvedka),
`notebooks/02_cleaning.ipynb` (poetapnaya ochistka, Restart & Run All),
`notebooks/colab_task.ipynb` (shag 8, zagruzit v Colab, otkryt dostup po ssylke).

Struktura `data`: `raw` (vneshnie CSV, tolko chtenie) →
`interim` (parquet, typed) → `processed` (clean.parquet, dataset.db).
Vosproizvodimost: udalit `interim`+`processed` i vypolnit komandy vyshe.

## Bazy dannykh

- SQLite: `sql/schema_sqlite.sql` (DDL iz DBeaver), zagruzka paketami
  `chunksize=50_000`, izmerenie zameny v otchete (tabl. 9).
- PostgreSQL: ustanovka sluzhby/konteyner, rol i baza, `.env` (obrazets `.env.example`),
  `sql/schema_postgres.sql`, poryadok: spravochniki → observations,
  sravnenie `to_sql(method='multi')` vs `COPY`, ER-diagramma `docs/er_diagram.png`.

## Rezultaty (kratko)

- Parquet 5.7 MB protiv CSV 293.7 MB (x51), chtenie 0.12 s protiv 3.49 s (x29).
- Skhema: pamyat 366 → 161 MB, fayl 5.7 → 3.6 MB, 7 category-stolbtsov.
- Polars bystree pandas: filtr x8, gruppirovka x4.5, sort x6, join x3.8.
- Ochistka ds1: strok 0% potery, znacheniy NaN 38.9% (porcha Excel-datami, obosnovano).
- SQLite: 260 stran, 64 pokazatelya, 1 048 575 nablyudeniy za 4.5 s, 37 MB
  (58 MB s indeksami); range-zapros s indeksom x4 bystree.
- Glavnaya nakhodka: ~39% `value` v ds1 isporcheno russkim Excel
  (`июн.55` vmesto 6.55) — klasse primer «tikhogo» razrusheniya dannykh.

Detali, tablitsy 6–9 i diagrammy — v otchete `docs/ОТЧЕТ_ЛР1.docx`
(sgadolu: ssylka na Colab, ssylka na GitHub).
