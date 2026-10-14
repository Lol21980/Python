-- Schema SQLite, 3NF. Sozdano v DBeaver, sokhraneno kak DDL.
PRAGMA journal_mode = WAL;

DROP TABLE IF EXISTS observations;
DROP TABLE IF EXISTS countries;
DROP TABLE IF EXISTS indicators;

CREATE TABLE countries (
  country_id   INTEGER PRIMARY KEY,
  country_code VARCHAR(8)   NOT NULL UNIQUE,
  country      VARCHAR(128) NOT NULL,
  region       VARCHAR(64),
  income_group VARCHAR(64)
);

CREATE TABLE indicators (
  indicator_id   INTEGER PRIMARY KEY,
  indicator_code VARCHAR(32)  NOT NULL UNIQUE,
  indicator_name VARCHAR(256) NOT NULL,
  indicator_topic VARCHAR(128),
  indicator_def  TEXT
);

CREATE TABLE observations (
  country_id   INTEGER NOT NULL REFERENCES countries(country_id),
  indicator_id INTEGER NOT NULL REFERENCES indicators(indicator_id),
  year         SMALLINT NOT NULL,
  value        REAL,  -- NULL = nablyudeniya net (WDI propuski + isporchennye Excel znacheniya)
  PRIMARY KEY (country_id, indicator_id, year)
);

CREATE INDEX idx_obs_year ON observations(year);
CREATE INDEX idx_obs_indicator ON observations(indicator_id);
CREATE INDEX idx_countries_region ON countries(region);
