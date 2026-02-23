#!/usr/bin/env python3
"""
BlackRoad Startup Metrics — MRR, ARR, churn, runway, headcount tracking.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional


DB_PATH = Path(os.environ.get("STARTUP_DB", "~/.blackroad/startup_metrics.db")).expanduser()


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS startups (
                id           TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                stage        TEXT NOT NULL DEFAULT 'seed',
                founded_date TEXT,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS metrics (
                id           TEXT PRIMARY KEY,
                startup_id   TEXT NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
                metric_type  TEXT NOT NULL,
                value        REAL NOT NULL,
                period       TEXT NOT NULL,
                notes        TEXT DEFAULT '',
                recorded_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS customers (
                id           TEXT PRIMARY KEY,
                startup_id   TEXT NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
                name         TEXT NOT NULL,
                plan         TEXT NOT NULL DEFAULT 'monthly',
                mrr          REAL NOT NULL DEFAULT 0,
                status       TEXT NOT NULL DEFAULT 'active',
                started_at   TEXT NOT NULL,
                churned_at   TEXT,
                notes        TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS employees (
                id           TEXT PRIMARY KEY,
                startup_id   TEXT NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
                name         TEXT NOT NULL,
                role         TEXT NOT NULL,
                department   TEXT NOT NULL DEFAULT 'general',
                salary       REAL NOT NULL DEFAULT 0,
                hired_at     TEXT NOT NULL,
                left_at      TEXT
            );
            CREATE TABLE IF NOT EXISTS funding_rounds (
                id           TEXT PRIMARY KEY,
                startup_id   TEXT NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
                round_name   TEXT NOT NULL,
                amount       REAL NOT NULL,
                valuation    REAL,
                closed_at    TEXT NOT NULL,
                investors    TEXT NOT NULL DEFAULT '[]',
                notes        TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_metrics_startup ON metrics(startup_id);
            CREATE INDEX IF NOT EXISTS idx_metrics_type ON metrics(metric_type);
            CREATE INDEX IF NOT EXISTS idx_customers_startup ON customers(startup_id);
        """)


@dataclass
class Startup:
    id: str
    name: str
    stage: str
    founded_date: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Startup":
        return cls(
            id=row["id"], name=row["name"], stage=row["stage"],
            founded_date=row["founded_date"], created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class Metric:
    id: str
    startup_id: str
    metric_type: str
    value: float
    period: str
    notes: str
    recorded_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Metric":
        return cls(
            id=row["id"], startup_id=row["startup_id"],
            metric_type=row["metric_type"], value=row["value"],
            period=row["period"], notes=row["notes"] or "",
            recorded_at=row["recorded_at"],
        )


class StartupMetricsService:

    def create_startup(self, name: str, stage: str = "seed", founded_date: str | None = None) -> Startup:
        sid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO startups(id, name, stage, founded_date, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (sid, name, stage, founded_date, now, now),
            )
        return Startup(id=sid, name=name, stage=stage, founded_date=founded_date,
                       created_at=now, updated_at=now)

    def record_metric(self, startup_id: str, metric_type: str, value: float,
                      period: str | None = None, notes: str = "") -> Metric:
        mid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        period = period or datetime.utcnow().strftime("%Y-%m")
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO metrics(id, startup_id, metric_type, value, period, notes, recorded_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (mid, startup_id, metric_type, value, period, notes, now),
            )
        return Metric(id=mid, startup_id=startup_id, metric_type=metric_type,
                      value=value, period=period, notes=notes, recorded_at=now)

    def add_customer(self, startup_id: str, name: str, mrr: float, plan: str = "monthly") -> dict:
        cid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO customers(id, startup_id, name, plan, mrr, started_at) VALUES (?,?,?,?,?,?)",
                (cid, startup_id, name, plan, mrr, now),
            )
        return {"id": cid, "name": name, "mrr": mrr, "plan": plan}

    def churn_customer(self, customer_id: str) -> None:
        now = datetime.utcnow().isoformat()
        with get_conn() as conn:
            conn.execute(
                "UPDATE customers SET status='churned', churned_at=? WHERE id=?",
                (now, customer_id),
            )

    def add_employee(self, startup_id: str, name: str, role: str,
                     department: str = "general", salary: float = 0.0) -> dict:
        eid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO employees(id, startup_id, name, role, department, salary, hired_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (eid, startup_id, name, role, department, salary, now),
            )
        return {"id": eid, "name": name, "role": role, "department": department, "salary": salary}

    def add_funding(self, startup_id: str, round_name: str, amount: float,
                    valuation: float | None = None, investors: list[str] | None = None) -> dict:
        fid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        invs = investors or []
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO funding_rounds(id, startup_id, round_name, amount, valuation, closed_at, investors) "
                "VALUES (?,?,?,?,?,?,?)",
                (fid, startup_id, round_name, amount, valuation, now, json.dumps(invs)),
            )
        return {"id": fid, "round": round_name, "amount": amount, "valuation": valuation}

    def calculate_mrr(self, startup_id: str) -> float:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT SUM(mrr) as total FROM customers WHERE startup_id=? AND status='active'",
                (startup_id,),
            ).fetchone()
        return round(row["total"] or 0.0, 2)

    def calculate_arr(self, startup_id: str) -> float:
        return round(self.calculate_mrr(startup_id) * 12, 2)

    def calculate_churn_rate(self, startup_id: str, period: str | None = None) -> dict:
        period = period or datetime.utcnow().strftime("%Y-%m")
        with get_conn() as conn:
            total_start = conn.execute(
                "SELECT COUNT(*) as c FROM customers WHERE startup_id=? AND started_at < ?",
                (startup_id, period + "-01"),
            ).fetchone()["c"]
            churned = conn.execute(
                "SELECT COUNT(*) as c FROM customers WHERE startup_id=? AND status='churned' "
                "AND churned_at LIKE ?",
                (startup_id, period + "%"),
            ).fetchone()["c"]
        rate = (churned / total_start * 100) if total_start > 0 else 0.0
        return {
            "period": period,
            "customers_at_start": total_start,
            "churned": churned,
            "churn_rate_pct": round(rate, 2),
        }

    def calculate_runway(self, startup_id: str, monthly_burn: float) -> dict:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT SUM(amount) as total FROM funding_rounds WHERE startup_id=?",
                (startup_id,),
            ).fetchone()
        total_raised = row["total"] or 0.0
        mrr = self.calculate_mrr(startup_id)
        net_burn = max(0, monthly_burn - mrr)
        runway_months = (total_raised / net_burn) if net_burn > 0 else float("inf")
        return {
            "total_raised": round(total_raised, 2),
            "mrr": mrr,
            "monthly_burn": monthly_burn,
            "net_burn": round(net_burn, 2),
            "runway_months": round(runway_months, 1) if runway_months != float("inf") else "∞",
        }

    def headcount(self, startup_id: str) -> dict:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT department, COUNT(*) as count, SUM(salary) as total_salary "
                "FROM employees WHERE startup_id=? AND left_at IS NULL GROUP BY department",
                (startup_id,),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) as c, SUM(salary) as s FROM employees WHERE startup_id=? AND left_at IS NULL",
                (startup_id,),
            ).fetchone()
        return {
            "total_headcount": total["c"],
            "total_salary_cost": round(total["s"] or 0, 2),
            "by_department": {r["department"]: {"count": r["count"], "salary": round(r["total_salary"] or 0, 2)} for r in rows},
        }

    def kpi_dashboard(self, startup_id: str, monthly_burn: float = 0) -> dict:
        mrr = self.calculate_mrr(startup_id)
        arr = self.calculate_arr(startup_id)
        churn = self.calculate_churn_rate(startup_id)
        runway = self.calculate_runway(startup_id, monthly_burn) if monthly_burn > 0 else {}
        hc = self.headcount(startup_id)
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM startups WHERE id=?", (startup_id,)).fetchone()
        startup_name = row["name"] if row else "Unknown"
        return {
            "startup": startup_name,
            "mrr": mrr,
            "arr": arr,
            "churn": churn,
            "runway": runway,
            "headcount": hc,
            "as_of": datetime.utcnow().isoformat(),
        }

    def metric_history(self, startup_id: str, metric_type: str) -> list[dict]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM metrics WHERE startup_id=? AND metric_type=? ORDER BY period",
                (startup_id, metric_type),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_startups(self) -> list[dict]:
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM startups ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def main() -> None:
    init_db()
    parser = argparse.ArgumentParser(prog="startup-metrics", description="BlackRoad Startup Metrics")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("create", help="Create startup")
    p.add_argument("name"); p.add_argument("--stage", default="seed")

    p = sub.add_parser("dashboard", help="Show KPI dashboard")
    p.add_argument("id"); p.add_argument("--burn", type=float, default=0)

    p = sub.add_parser("add-customer", help="Add customer")
    p.add_argument("startup_id"); p.add_argument("name"); p.add_argument("mrr", type=float)

    p = sub.add_parser("add-employee", help="Add employee")
    p.add_argument("startup_id"); p.add_argument("name"); p.add_argument("role")
    p.add_argument("--dept", default="general"); p.add_argument("--salary", type=float, default=0)

    p = sub.add_parser("fund", help="Record funding round")
    p.add_argument("startup_id"); p.add_argument("round_name"); p.add_argument("amount", type=float)

    p = sub.add_parser("mrr", help="Calculate MRR")
    p.add_argument("id")

    p = sub.add_parser("runway", help="Calculate runway")
    p.add_argument("id"); p.add_argument("burn", type=float)

    p = sub.add_parser("metric", help="Record a custom metric")
    p.add_argument("startup_id"); p.add_argument("type"); p.add_argument("value", type=float)

    p = sub.add_parser("list", help="List startups")

    args = parser.parse_args()
    svc = StartupMetricsService()

    if args.command == "create":
        s = svc.create_startup(args.name, stage=args.stage)
        print(json.dumps({"id": s.id, "name": s.name}, indent=2))
    elif args.command == "dashboard":
        print(json.dumps(svc.kpi_dashboard(args.id, monthly_burn=args.burn), indent=2))
    elif args.command == "add-customer":
        print(json.dumps(svc.add_customer(args.startup_id, args.name, args.mrr), indent=2))
    elif args.command == "add-employee":
        print(json.dumps(svc.add_employee(args.startup_id, args.name, args.role,
                                           department=args.dept, salary=args.salary), indent=2))
    elif args.command == "fund":
        print(json.dumps(svc.add_funding(args.startup_id, args.round_name, args.amount), indent=2))
    elif args.command == "mrr":
        print(f"MRR: ${svc.calculate_mrr(args.id):,.2f}")
        print(f"ARR: ${svc.calculate_arr(args.id):,.2f}")
    elif args.command == "runway":
        print(json.dumps(svc.calculate_runway(args.id, args.burn), indent=2))
    elif args.command == "metric":
        m = svc.record_metric(args.startup_id, args.type, args.value)
        print(json.dumps({"id": m.id, "type": m.metric_type, "value": m.value}, indent=2))
    elif args.command == "list":
        print(json.dumps(svc.list_startups(), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
