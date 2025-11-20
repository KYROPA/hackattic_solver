Прежде чем приступить я установил докер,сильно тут рассказывать нечего, в краце: я на Manjaro, устанавливал через AUR, повозился с ядром Kernel. 

Шаг 1
сделал несколько контейнеров и связал их в единую сеть hackattic-net. Решил хранить пароли в Vault, чтобы было безопаснее. И экспортировал токен.

docker network create hackattic-net

1. Postgres в отдельном контейнере
docker run --name challenge-pg \
  --network hackattic-net \
  -e POSTGRES_PASSWORD=passwd \
  -d postgres:16

2. Vault в отдельном контейнере
docker run --name dev-vault \
  --network hackattic-net \
  -d \
  -p 8200:8200 \
  -e 'VAULT_DEV_ROOT_TOKEN_ID=root' \
  -e 'VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200' \
  hashicorp/vault:latest

Шаг 2
Сделал скрипт и докерфайл.

Ниже тело скрипта с описанием

```

#!/usr/bin/env python3
import os
import base64
import gzip
import requests
import psycopg2



# Настройки Vault и Postgres


# Адрес Vault — внутри docker-сети это dev-vault:8200, но мы переопределить через ENV.

VAULT_ADDR = os.environ.get("VAULT_ADDR", "http://dev-vault:8200")
VAULT_TOKEN = os.environ.get("VAULT_TOKEN", "root")  # dev-режим, root-токен

# Подключение к postgres-контейнеру challenge-pg в сети hackattic-net
PG_CONFIG = {
    "host": "challenge-pg",   # имя контейнера Postgres
    "port": 5432,
    "user": "postgres",
    "password": "passwd",
    "dbname": "postgres",
}

# Базовый URL Hackattic
BASE_URL = "https://hackattic.com"



# Работа с Vault


def get_secret_from_vault(path: str) -> dict:

# Забираем секрет из Vault KV v2 по пути secret/data/<path> и возвращает словарь с ключами, которые лежат внутри "data".

    url = f"{VAULT_ADDR}/v1/secret/data/{path}"
    headers = {"X-Vault-Token": VAULT_TOKEN}
    resp = requests.get(url, headers=headers, timeout=5)
    resp.raise_for_status()
    payload = resp.json()
    # KV v2 хранит данные в data["data"]
    return payload["data"]["data"]


# Берем токен из Vault
vault_secret = get_secret_from_vault("hackattic")
TOKEN = vault_secret["HACKATTIC_TOKEN"]

PROBLEM_URL = f"{BASE_URL}/challenges/backup_restore/problem?access_token={TOKEN}"
SOLVE_URL = f"{BASE_URL}/challenges/backup_restore/solve?access_token={TOKEN}"



# Получение и восстановление дампа


def get_problem_dump() -> str:

    # Скачиваем /problem, декодируем base64 + gzip,

    resp = requests.get(PROBLEM_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    dump_b64 = data["dump"]

    compressed = base64.b64decode(dump_b64)
    sql_bytes = gzip.decompress(compressed)
    sql_text = sql_bytes.decode("utf-8")
    return sql_text


def recreate_db():
    """
    Переподнимаем базу challenge_db:
    DROP DATABASE IF EXISTS + CREATE DATABASE.
    Делаем это через подключение к postgres (system db).
    """
    cfg = PG_CONFIG.copy()
    conn = psycopg2.connect(**cfg)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DROP DATABASE IF EXISTS challenge_db;")
    cur.execute("CREATE DATABASE challenge_db;")
    cur.close()
    conn.close()


def restore_dump(sql_text: str):

    # Подключаемся к challenge_db и выполняем SQL дамп.

    cfg = PG_CONFIG.copy()
    cfg["dbname"] = "challenge_db"
    conn = psycopg2.connect(**cfg)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql_text)
    cur.close()
    conn.close()


# Чтение данных и отправка решения

def get_alive_ssns():
    """
    Достаём все ssn из criminal_records, где status = 'alive'.
    Возвращаем список строк.
    """
    cfg = PG_CONFIG.copy()
    cfg["dbname"] = "challenge_db"
    conn = psycopg2.connect(**cfg)
    cur = conn.cursor()
    cur.execute(
        "SELECT ssn FROM criminal_records WHERE status = 'alive';"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


def submit_solution(alive_ssns):
    """
    Отправляем JSON на /solve.
    Формат: {"alive_ssns": [...]}.
    """
    payload = {"alive_ssns": alive_ssns}
    resp = requests.post(SOLVE_URL, json=payload, timeout=10)
    resp.raise_for_status()
    print("Solve response:", resp.text)


# ----------------------------
# main()
# ----------------------------

def main():
    print("[*] Fetching problem from Hackattic...")
    sql_text = get_problem_dump()

    print("[*] Recreating challenge_db in Postgres...")
    recreate_db()

    print("[*] Restoring dump into challenge_db...")
    restore_dump(sql_text)

    print("[*] Querying alive SSNs...")
    alive_ssns = get_alive_ssns()
    print(f"[*] Got {len(alive_ssns)} SSNs: {alive_ssns}")

    print("[*] Submitting solution to Hackattic...")
    submit_solution(alive_ssns)

    print("[✓] Done.")


if __name__ == "__main__":
    main()

```
    
И конечный вывод что все прошло верно

```

SET
SET
SET
SET
SET
 set_config
------------

(1 row)

SET
SET
SET
SET
COMMENT
CREATE EXTENSION
COMMENT
SET
psql:/tmp/tmpeew4gxqv:42: ERROR:  tables declared WITH OIDS are not supported
CREATE TABLE
ALTER TABLE
CREATE SEQUENCE
ALTER TABLE
ALTER SEQUENCE
ALTER TABLE
COPY 87
 setval
--------
     87
(1 row)

ALTER TABLE
[*] Fetching problem from Hackattic...
[*] Recreating challenge_db in Postgres...
[*] Restoring dump into challenge_db...
[*] Querying alive SSNs...
[*] Got 32 SSNs: ['037-61-5291', '154-10-1047', '015-40-0347', '605-69-7022', '413-44-2246', '481-82-5375', '829-44-6199', '824-16-0495', '879-08-1318', '240-45-5535', '521-34-4303', '171-77-3421', '147-10-1536', '138-67-7604', '320-20-5454', '207-11-2247', '837-62-2152', '626-41-8716', '030-41-6953', '035-42-6805', '036-87-2436', '235-43-9796', '456-05-4324', '036-60-4702', '823-35-0387', '267-58-2646', '400-16-6903', '502-92-9355', '067-93-0667', '592-33-7040', '732-79-4653', '808-62-8172']
[*] Submitting solution to Hackattic...
Solve response: {"result": "passed"}
[✓] Done.

```
