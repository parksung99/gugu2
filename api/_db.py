"""Small Supabase REST client used by Vercel Python functions."""
import json
import os
from urllib.parse import quote

import requests


SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://yattlqdsnrqeqzvcuvuu.supabase.co").rstrip("/")
SUPABASE_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
SUPABASE_ANON_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlhdHRscWRzbnJxZXF6dmN1dnV1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU0Mzc4NDMsImV4cCI6MjA5MTAxMzg0M30.OXYzBYsMHg3ryW7DDr5xljXrgCkL92EIQS2LunAabag",
)


class _Result:
    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count


class _Query:
    def __init__(self, table, auth_token=None, method="GET", payload=None):
        self.table = table
        self.auth_token = auth_token
        self.method = method
        self.payload = payload
        self.params = []
        self.headers = {}
        self._single = False

    def select(self, columns="*", count=None):
        self.method = "GET"
        self.params.append(("select", columns))
        if count == "exact":
            self.headers["Prefer"] = "count=exact"
        return self

    def insert(self, payload):
        self.method = "POST"
        self.payload = payload
        self.headers["Prefer"] = "return=representation"
        return self

    def update(self, payload):
        self.method = "PATCH"
        self.payload = payload
        self.headers["Prefer"] = "return=representation"
        return self

    def delete(self):
        self.method = "DELETE"
        self.headers["Prefer"] = "return=representation"
        return self

    def eq(self, column, value):
        self.params.append((column, f"eq.{value}"))
        return self

    def neq(self, column, value):
        self.params.append((column, f"neq.{value}"))
        return self

    def in_(self, column, values):
        joined = ",".join(str(v) for v in values)
        self.params.append((column, f"in.({joined})"))
        return self

    def order(self, column, desc=False):
        direction = "desc" if desc else "asc"
        self.params.append(("order", f"{column}.{direction}"))
        return self

    def range(self, start, end):
        self.headers["Range-Unit"] = "items"
        self.headers["Range"] = f"{start}-{end}"
        return self

    def limit(self, count):
        self.params.append(("limit", str(count)))
        return self

    def single(self):
        self._single = True
        self.headers["Accept"] = "application/vnd.pgrst.object+json"
        return self

    def execute(self):
        api_key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
        bearer = SUPABASE_SERVICE_KEY or self.auth_token or SUPABASE_ANON_KEY

        headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
            **self.headers,
        }
        if not self._single:
            headers.setdefault("Accept", "application/json")

        response = requests.request(
            self.method,
            f"{SUPABASE_URL}/rest/v1/{quote(self.table)}",
            headers=headers,
            params=self.params,
            json=self.payload,
            timeout=20,
        )

        if response.status_code >= 400:
            raise RuntimeError(f"Supabase REST {response.status_code}: {response.text}")

        if response.status_code == 204 or not response.text:
            data = None
        else:
            data = response.json()

        count = None
        content_range = response.headers.get("content-range") or response.headers.get("Content-Range")
        if content_range and "/" in content_range:
            total = content_range.rsplit("/", 1)[-1]
            if total.isdigit():
                count = int(total)

        return _Result(data, count)


class _DB:
    def __init__(self, auth_token=None):
        self.auth_token = auth_token

    def table(self, name):
        return _Query(name, auth_token=self.auth_token)


_client = _DB()


def get_db(auth_token=None) -> _DB:
    return _DB(auth_token) if auth_token else _client


def ok(data, status=200):
    return json.dumps({"ok": True, "data": data}), status, _cors_headers()


def err(message, status=400):
    return json.dumps({"ok": False, "error": message}), status, _cors_headers()


def _cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    }
