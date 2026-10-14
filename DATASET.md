# Pasport nabora dannykh (DATASET.md)

Variant 12: «Dinamika chislennosti naseleniya po stranam mira».
Istochnik: World Bank Open Data — World Development Indicators (WDI),
arhiv `WDI_CSV.zip` (`https://databank.worldbank.org/data/download/WDI_CSV.zip`),
litsenziya CC BY 4.0, data obrashcheniya 30.06.2026 (sm. `реестр_ссылок.csv`).

Osnovnoy fayl raboty (LR1): `1_датасет_население_возраст_и_пол.csv`
(293.7 MB, 1 048 575 strok — rovno limit Excel, dannye usecheny).
Dopolnitelno: `2_датасет_..._урбанизация.csv` (526.6 MB),
`3_датасет_..._брачность.csv` (603.1 MB) — dlya analiza soedineniya.

Format: CSV, kodirovka UTF-8 s BOM, razdelitel `;`
(desyatichnyy razdelitel v chasti faylov — zapyataya, sm. defekty).
Dvizhenie: `RAW (vneshnyaya papka, tolko chtenie)` →
`data/interim/source_snappy.parquet` (serializatsiya) →
`data/interim/source_typed.parquet` (skhema) →
`data/processed/clean.parquet` (ochistka, vkhod sled. laboratornykh).

## Stolbtsy (11 iskhodnykh)

| # | Stolbets (ru) | EN (posle rename) | Smysl | Tip (iskh.) | Prigodnost |
|---|---|---|---|---|---|
| 1 | Страна | country | Nazvanie strany/territorii (angl.) | tekst | kategoriya (260 unikalnykh s agregatami) |
| 2 | Код страны | country_code | Kod ekonomiki WB (ISO3 + agregaty WLD, EUU…) | tekst | klyuch, kategoriya |
| 3 | Регион | region | Georegion WB | tekst, ~19% pusto (agregaty) | kategoriya + NULL |
| 4 | Группа дохода | income_group | Gruppa dokhoda WB | tekst, ~19% pusto | kategoriya + NULL |
| 5 | Код показателя | indicator_code | Kod WDI (SP.POP.* — 64 sht.) | tekst | klyuch, kategoriya |
| 6 | Название показателя | indicator_name | Polnoe nazvanie | tekst-dubl | kategoriya (v sprav. 3NF) |
| 7 | Тема показателя | indicator_topic | Rubrika WDI | tekst (3 znacheniya) | kategoriya |
| 8 | Определение показателя | indicator_def | Opredelenie (angl., dlinnoe) | tekst-dubl | string, v sprav. 3NF |
| 9 | Год | year | God nablyudeniya, 1960–2024 | chislo | int16 |
| 10 | Значение | value | Velichina pokazatelya (raznye edinitsy!) | chislo-tekst | float64 + NULL (38.9% isporcheno) |
| 11 | Сноска | footnote | Sluzhebnoe pole | tekst, ~96% pusto | UDALENO |

Posle ochistki: 10 poley + 4 flaga
(`flag_bad_year`, `flag_bad_value`, `flag_out_iqr`, `flag_out_sigma`).

## Pokazateli ds1 (64, vse SP.POP)

Struktura naseleniya: `SP.POP.TOTL*` (vsego/pol/doli),
vozrastnye gruppy `SP.POP.{0004…80UP}.*`,
trudosposobnye `SP.POP.1564.*`, pozhilye `SP.POP.65UP.*`,
zavisimost `SP.POP.DPND*`, rost `SP.POP.GROW`,
rozhdaemost `SP.POP.BRTH.MF`, nauka `SP.POP.SCIE/TECH.RD.P6`
(malo nablyudeniy: 2449/1295 — redkie, no sokhraneny).

Prostranstvennyy okhvat: 260 kodov (strany + agregaty WB).
Vremennoy: 1960–2024 (65 let; 2025 v fayle net, zayavlennye 1960–2025 ne podtverdilis).
Klyuch: (country_code, indicator_code, year) — dublikatov 0.

## Obnaruzhennye defekty (plan ochistki)

1. **Usechenie do limita Excel** (1 048 575 strok): fayly — sokhranennye iz Excel,
   khvost dannykh poteryan; ds2/ds3 iz-za etogo soderzhat postoronnie
   indikatory (1357/1395 vmesto zayavlennykh 22/20) i ne yavlyayutsya tematicheskimi.
2. **Porcha chisel Excel-avtoformatom dat (ds1, 38.9%)**: 404 127 znacheniy vida
   `июн.55`, `фев.92` + 3 293 vida `01.май` — russkiy Excel prevratil desyatichnye
   doli (napr. 6.55) v «mesyats.god». Vosstanovlenie neodnoznachno →
   v NaN, stroki sokhraneny (poterya strok 0%, poterya znacheniy 38.9%).
3. **Smeshannyy desyatichnyy razdelitel**: ds1 — tochka; ds2/ds3 — chast
   s zapyatoy (`1,77872E+12`, ds2: 8 856, ds3: 28 611) + tochka.
   Lechenie: normalizatsiya zapyatoy v tochku do `to_numeric(errors='coerce')`.
4. **Pustye Region/Income (~19%)** — zakonomernye NULL u agregatov; sokhraneny.
5. **Footnote ~96% pusto** — stolbets udalen.
6. **Tekstovye dubli** (name/topic/def povtoryayutsya na kazhduyu stroku) —
   category + vynesenie v spravochniki 3NF.
7. **Nevernye tipy**: vse chitalos kak tekst/obekty (366 MB) →
   int16/float64/category (160 MB).
8. **Smeshenie urovney**: strany + agregaty (World, regiony) v odnoy tablitse —
   otmecheno, dlya strogogo analiza agregaty filtruyutsya po spisku kodov.
9. **Raznye edinitsy v `value`** (cheloveki, %, tempy) — agreggirovat tolko
   vnutri pokazatelya; srednee po teme v otchete pomecheno kak tekhnicheskiy zapros.
10. **Vybrosy**: IQR pometil 57 750 (5.5%), 3σ — 8 620 (0.8%) —
    na skoshennykh raspredeleniyakh (Kitay/Indiya vs mikrogosudarstva) IQR
    daet lozhnye srabotki → tolko flagi, udaleniya net.
11. **Redkie kategorii**: topic `Infrastructure: Technology` (3 744 stroki) → OTHER.
12. **Biznes-pravila**: godov v budushchem net (0), otrits. naseleniya net (0).

## Svodka «bylo — stalo» (ds1)

Strok: 1 048 575 → 1 048 575 (poterya 0%).
Stolbtsov: 11 → 14 (minus footnote, plyus 4 flaga).
`value`: NaN 407 420 (38.9%, prichina — p.2).
Konveyer idempotenten (povtor dayot tot zhe hash),
`clean.parquet` (zstd, 5.0 MB) == rezultat notebooka (sverka hash v otchete).
