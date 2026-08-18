"""
expiry_risk.py — Batch-level expiry risk prediction

Given: batch stock quantity + expiry_date + avg daily consumption rate
→ Flag batches that will likely expire before being fully consumed
→ Output: risk score, units_at_risk, days_until_expiry

Writes flagged batches to `anomalies` table with rule_triggered = 'EXPIRY_RISK'
"""

import os
from datetime import date, datetime
from typing import Optional

from supabase import create_client, Client


# ── core logic ────────────────────────────────────────────────────────────────

def compute_expiry_risk(
    batch_id: str,
    drug_id: str,
    quantity_remaining: float,
    expiry_date: date,
    avg_daily_consumption: float,
    today: Optional[date] = None,
) -> dict:
    """
    Determine if a batch is at risk of expiring before it's consumed.

    Returns:
    {
      batch_id, drug_id,
      days_until_expiry: int,
      units_at_risk: float,       # units that will remain when batch expires
      risk_score: float,          # 0.0 – 1.0 (1.0 = entire batch will expire)
      is_at_risk: bool,
      risk_label: str,            # "HIGH" | "MEDIUM" | "LOW" | "SAFE"
      details: str,
    }
    """
    today = today or date.today()

    if isinstance(expiry_date, str):
        expiry_date = date.fromisoformat(expiry_date)

    days_until_expiry = (expiry_date - today).days

    if days_until_expiry <= 0:
        return _risk_result(
            batch_id, drug_id,
            days_until_expiry=0,
            units_at_risk=quantity_remaining,
            risk_score=1.0,
            is_at_risk=True,
            risk_label="EXPIRED",
            details=f"Batch already expired on {expiry_date}. {quantity_remaining:.0f} units wasted.",
        )

    if avg_daily_consumption <= 0:
        # No consumption data → treat entire batch as at risk
        return _risk_result(
            batch_id, drug_id,
            days_until_expiry=days_until_expiry,
            units_at_risk=quantity_remaining,
            risk_score=1.0,
            is_at_risk=True,
            risk_label="HIGH",
            details=f"No consumption data. {quantity_remaining:.0f} units may expire in {days_until_expiry}d.",
        )

    days_to_consume = quantity_remaining / avg_daily_consumption
    units_consumable = avg_daily_consumption * days_until_expiry
    units_at_risk = max(0, quantity_remaining - units_consumable)
    risk_score = min(1.0, units_at_risk / quantity_remaining) if quantity_remaining > 0 else 0.0

    if risk_score >= 0.75:
        risk_label = "HIGH"
    elif risk_score >= 0.40:
        risk_label = "MEDIUM"
    elif risk_score > 0:
        risk_label = "LOW"
    else:
        risk_label = "SAFE"

    is_at_risk = risk_score > 0.10  # >10% of batch at risk → flag it

    details = (
        f"{units_at_risk:.0f} of {quantity_remaining:.0f} units ({risk_score*100:.0f}%) "
        f"likely to expire by {expiry_date} "
        f"(consumption rate: {avg_daily_consumption:.1f}/day, "
        f"days to consume: {days_to_consume:.0f}, "
        f"days until expiry: {days_until_expiry})."
    )

    return _risk_result(
        batch_id, drug_id,
        days_until_expiry=days_until_expiry,
        units_at_risk=round(units_at_risk, 1),
        risk_score=round(risk_score, 3),
        is_at_risk=is_at_risk,
        risk_label=risk_label,
        details=details,
    )


def _risk_result(batch_id, drug_id, **kwargs) -> dict:
    return {"batch_id": batch_id, "drug_id": drug_id, **kwargs}


# ── batch scan: pull from Supabase, flag, write anomalies ────────────────────

def scan_all_batches_for_expiry_risk(
    forecast_results: list[dict],
) -> list[dict]:
    """
    Pull all active batches from Supabase, run expiry risk for each,
    write flagged batches to `anomalies` table.

    forecast_results: output of run_all_forecasts() — provides avg_daily_consumption per drug_id
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")

    # Build avg_daily lookup
    daily_lookup = {r["drug_id"]: r["avg_daily_consumption"] for r in forecast_results}

    flagged = []

    if not url or not key:
        print("⚠️  Supabase not configured — running on mock batch data")
        flagged = _run_on_mock_batches(daily_lookup)
    else:
        supabase: Client = create_client(url, key)
        batches = supabase.table("batches").select("id, drug_id, batch_number, expiry_date").execute().data

        for b in batches:
            # Get stock for this batch from scan_events or a stock_levels table
            # For now, mock as 200 units if we can't get it
            qty = _get_batch_quantity(supabase, b["id"])
            avg_daily = daily_lookup.get(b["drug_id"], 10.0)

            risk = compute_expiry_risk(
                batch_id=b["id"],
                drug_id=b["drug_id"],
                quantity_remaining=qty,
                expiry_date=b["expiry_date"],
                avg_daily_consumption=avg_daily,
            )

            if risk["is_at_risk"]:
                flagged.append(risk)
                _write_anomaly(supabase, b, risk)

    if flagged:
        print(f"\n⚠️  {len(flagged)} batches flagged for expiry risk:")
        for r in flagged:
            print(f"  {r['risk_label']:6s} | batch {r['batch_id']} | {r['units_at_risk']} units | {r['details'][:60]}...")
    else:
        print("✅ No batches at expiry risk")

    return flagged


def _get_batch_quantity(supabase: Client, batch_id: str) -> float:
    """Query current remaining quantity for a batch. Falls back to 200 if unknown."""
    try:
        # This assumes a stock_levels view or similar; adjust to your backend schema
        result = supabase.table("scan_events").select("quantity").eq("batch_id", batch_id).execute()
        if result.data:
            return sum(r.get("quantity", 0) for r in result.data if r.get("quantity"))
    except Exception:
        pass
    return 200.0  # fallback mock


def _write_anomaly(supabase: Client, batch: dict, risk: dict) -> None:
    supabase.table("anomalies").insert({
        "batch_id": batch["id"],
        "rule_triggered": "EXPIRY_RISK",
        "details": risk["details"],
        "resolved": False,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()


# ── mock data for offline testing ─────────────────────────────────────────────

def _run_on_mock_batches(daily_lookup: dict) -> list[dict]:
    mock_batches = [
        {"id": "batch_001", "drug_id": "drug_001", "expiry_date": "2025-03-15", "quantity": 500},
        {"id": "batch_002", "drug_id": "drug_002", "expiry_date": "2025-02-01", "quantity": 800},
        {"id": "batch_003", "drug_id": "drug_003", "expiry_date": "2026-12-31", "quantity": 200},
        {"id": "batch_004", "drug_id": "drug_005", "expiry_date": "2025-01-20", "quantity": 50},
    ]
    flagged = []
    for b in mock_batches:
        avg_daily = daily_lookup.get(b["drug_id"], 10.0)
        risk = compute_expiry_risk(
            batch_id=b["id"],
            drug_id=b["drug_id"],
            quantity_remaining=b["quantity"],
            expiry_date=b["expiry_date"],
            avg_daily_consumption=avg_daily,
        )
        if risk["is_at_risk"]:
            flagged.append(risk)
    return flagged


# ── standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from datetime import date, timedelta

    today = date.today()

    tests = [
        ("batch_A", "drug_001", 500, today + timedelta(days=10), 80.0),   # HIGH risk — expires in 10d, 80/day needed
        ("batch_B", "drug_002", 500, today + timedelta(days=60), 10.0),   # SAFE — 50 days consumption
        ("batch_C", "drug_003", 1000, today + timedelta(days=30), 15.0),  # MEDIUM — 66 days to consume, 30 left
        ("batch_D", "drug_004", 100, today - timedelta(days=1), 5.0),     # EXPIRED
    ]

    print("Expiry risk test cases:\n")
    for args in tests:
        r = compute_expiry_risk(*args)
        print(f"  [{r['risk_label']:7s}] {r['details']}")