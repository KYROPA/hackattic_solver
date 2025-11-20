#!/usr/bin/env python3
import os
import base64
import gzip
import requests
import psycopg2
import subprocess
import tempfile


# Настройки Vault и Postgres

VAULT_ADDR = os.environ.get("VAULT_ADDR", "http://dev-vault:8200")
VAULT_TOKEN = os.environ.get("VAULT_TOKEN", "root") 

PG_CONFIG = {
    "host": "challenge-pg",
    "port": 5432,
    "user": "postgres",
    "password": "passwd",
    "dbname": "postgres",
}

BASE_URL = "https://hackattic.com"



# Работа с Vault

def get_secret_from_vault(path: str) -> dict:
    url = f"{VAULT_ADDR}/v1/secret/data/{path}"
    headers = {"X-Vault-Token": VAULT_TOKEN}
    resp = requests.get(url, headers=headers, timeout=5)
    resp.raise_for_status()
    payload = resp.json()
    return payload["data"]["data"]


vault_secret = get_secret_from_vault("hackattic")
TOKEN = vault_secret["HACKATTIC_TOKEN"]

PROBLEM_URL = f"{BASE_URL}/challenges/backup_restore/problem?access_token={TOKEN}"
SOLVE_URL = f"{BASE_URL}/challenges/backup_restore/solve?access_token={TOKEN}"


# Получение и восстановление дампа

def get_problem_dump() -> str:

    resp = requests.get(PROBLEM_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    dump_b64 = data["dump"]

    compressed = base64.b64decode(dump_b64)
    sql_bytes = gzip.decompress(compressed)
    sql_text = sql_bytes.decode("utf-8")
    return sql_text


def recreate_db():
    cfg = PG_CONFIG.copy()
    conn = psycopg2.connect(**cfg)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DROP DATABASE IF EXISTS challenge_db;")
    cur.execute("CREATE DATABASE challenge_db;")
    cur.close()
    conn.close()


def restore_dump(sql_text: str):
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(sql_text)
        temp_path = f.name
    env = os.environ.copy()
    env["PGPASSWORD"] = PG_CONFIG["password"]
    subprocess.run(
        [
            "psql",
            "-h", PG_CONFIG["host"],
            "-p", str(PG_CONFIG["port"]),
            "-U", PG_CONFIG["user"],
            "-d", "challenge_db",
            "-f", temp_path,
        ],
        check=True,
        env=env,
    )


# Чтение данных и отправка решения

def get_alive_ssns():
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
    payload = {"alive_ssns": alive_ssns}
    resp = requests.post(SOLVE_URL, json=payload, timeout=10)
    resp.raise_for_status()
    print("Solve response:", resp.text)



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
