"""Document store with two backends: SQLite (default, zero-setup) and DynamoDB (AWS)."""
from __future__ import annotations
import json
import sqlite3
import threading
import os
from typing import Optional


class SqliteStore:
    name = "sqlite"

    def __init__(self, path: str):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS docs(kind TEXT, id TEXT, doc TEXT, PRIMARY KEY(kind,id))")
        self._db.execute("CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY, value INTEGER)")
        self._db.commit()

    def put(self, kind: str, id: str, doc: dict) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO docs VALUES(?,?,?)", (kind, id, json.dumps(doc)))
            self._db.commit()

    def get(self, kind: str, id: str) -> Optional[dict]:
        with self._lock:
            r = self._db.execute("SELECT doc FROM docs WHERE kind=? AND id=?", (kind, id)).fetchone()
        return json.loads(r[0]) if r else None

    def list(self, kind: str) -> list:
        with self._lock:
            rows = self._db.execute("SELECT doc FROM docs WHERE kind=?", (kind,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def put_if_absent(self, kind: str, id: str, doc: dict) -> bool:
        with self._lock:
            cur = self._db.execute("INSERT OR IGNORE INTO docs VALUES(?,?,?)", (kind, id, json.dumps(doc)))
            self._db.commit()
            return cur.rowcount == 1

    def incr(self, name: str, n: int = 1) -> int:
        with self._lock:
            self._db.execute("INSERT OR IGNORE INTO counters VALUES(?,0)", (name,))
            self._db.execute("UPDATE counters SET value=value+? WHERE name=?", (n, name))
            self._db.commit()
            return self._db.execute("SELECT value FROM counters WHERE name=?", (name,)).fetchone()[0]

    def counter(self, name: str) -> int:
        with self._lock:
            r = self._db.execute("SELECT value FROM counters WHERE name=?", (name,)).fetchone()
        return int(r[0]) if r else 0


class DynamoStore:
    """Single-table layout: pk=k (kind), sk=i (id), doc=JSON string. Counters use atomic ADD.
    UNVERIFIED against a live account in this build; see infra/template.yaml and docs/DEPLOY_AWS.md."""
    name = "dynamodb"

    def __init__(self, table: str, region: str):
        import boto3
        self.t = boto3.resource("dynamodb", region_name=region).Table(table)

    def put(self, kind, id, doc):
        self.t.put_item(Item={"k": kind, "i": id, "doc": json.dumps(doc)})

    def get(self, kind, id):
        r = self.t.get_item(Key={"k": kind, "i": id}).get("Item")
        return json.loads(r["doc"]) if r else None

    def list(self, kind):
        from boto3.dynamodb.conditions import Key
        out, kw = [], {"KeyConditionExpression": Key("k").eq(kind)}
        while True:
            r = self.t.query(**kw)
            out += [json.loads(i["doc"]) for i in r["Items"]]
            if "LastEvaluatedKey" not in r:
                return out
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]

    def put_if_absent(self, kind, id, doc):
        try:
            self.t.put_item(Item={"k": kind, "i": id, "doc": json.dumps(doc)},
                            ConditionExpression="attribute_not_exists(k)")
            return True
        except self.t.meta.client.exceptions.ConditionalCheckFailedException:
            return False

    def incr(self, name, n=1):
        r = self.t.update_item(Key={"k": "_counter", "i": name}, UpdateExpression="ADD n :d",
                               ExpressionAttributeValues={":d": n}, ReturnValues="UPDATED_NEW")
        return int(r["Attributes"]["n"])

    def counter(self, name):
        r = self.t.get_item(Key={"k": "_counter", "i": name}).get("Item")
        return int(r["n"]) if r else 0


def make_store(cfg):
    if cfg.store == "dynamodb":
        return DynamoStore(cfg.dynamo_table, cfg.aws_region)
    return SqliteStore(cfg.sqlite_path)
