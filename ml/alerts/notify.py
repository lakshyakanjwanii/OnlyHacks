"""
notify.py — Alert dispatch for stockout, anomaly, and expiry-risk events

sendAlert(type, message, recipient, channel)
  channel: "whatsapp" (primary) | "sms" (fallback)

Alert triggers:
  1. predicted_stockout_date within STOCKOUT_WARN_DAYS days
  2. New row in `anomalies` table (Supabase Realtime subscription)
  3. Expiry-risk batch flagged

Sent alerts are written to the `alerts` table.
"""

import os
import json
import asyncio
from datetime import datetime, date
from typing import Literal, Optional

import httpx
from supabase import create_client, Client

# ── config ────────────────────────────────────────────────────────────────────

STOCKOUT_WARN_DAYS = 14          # alert if stockout predicted within this window
AlertType = Literal["STOCKOUT_RISK", "ANOMALY", "EXPIRY_RISK"]
Channel = Literal["whatsapp", "sms"]

# Default recipients (override via env or DB)
DEFAULT_RECIPIENTS = os.environ.get(
    "ALERT_RECIPIENTS",
    "+919999999999"              # comma-separated phone numbers with country code
).split(",")

# WhatsApp Cloud API
WA_PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID", "")
WA_ACCESS_TOKEN = os.environ.get("WA_ACCESS_TOKEN", "")
WA_API_VERSION = "v19.0"

# Twilio SMS (fallback)
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")


# ── main sendAlert function ───────────────────────────────────────────────────

async def sendAlert(
    alert_type: AlertType,
    message: str,
    recipient: str,
    channel: Channel = "whatsapp",
) -> dict:
    """
    Dispatch an alert via WhatsApp or SMS.

    Args:
        alert_type: "STOCKOUT_RISK" | "ANOMALY" | "EXPIRY_RISK"
        message:    Human-readable alert text
        recipient:  Phone number with country code, e.g. "+919876543210"
        channel:    "whatsapp" (primary) or "sms" (fallback)

    Returns:
        {"success": bool, "channel": str, "provider_response": dict}
    """
    print(f"[ALERT] {alert_type} → {recipient} via {channel}: {message[:60]}...")

    success = False
    provider_response = {}

    try:
        if channel == "whatsapp":
            if not WA_PHONE_NUMBER_ID or not WA_ACCESS_TOKEN:
                print("  ⚠️  WhatsApp credentials not set — falling back to SMS")
                channel = "sms"
            else:
                provider_response = await _send_whatsapp(recipient, message)
                success = provider_response.get("messages") is not None

        if channel == "sms":
            if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
                print("  ⚠️  Twilio credentials not set — logging alert only")
                provider_response = {"status": "logged_only"}
                success = True  # don't crash pipeline if alerts aren't configured
            else:
                provider_response = await _send_sms(recipient, message)
                success = provider_response.get("status") in ("queued", "sent")

    except Exception as e:
        provider_response = {"error": str(e)}
        print(f"  ❌ Alert failed: {e}")

    await _write_alert_to_db(alert_type, message, recipient, channel, success)

    return {"success": success, "channel": channel, "provider_response": provider_response}


# ── trigger functions (called by the pipeline) ────────────────────────────────

async def alert_stockout_risk(drug_name: str, stockout_date: str, current_stock: float) -> None:
    """Fire when predicted_stockout_date is within STOCKOUT_WARN_DAYS."""
    today = date.today()
    days_left = (date.fromisoformat(stockout_date) - today).days

    msg = (
        f"🔴 STOCKOUT ALERT — {drug_name}\n"
        f"Current stock: {current_stock:.0f} units\n"
        f"Predicted stockout: {stockout_date} ({days_left} days)\n"
        f"Action required: Place reorder immediately.\n"
        f"— Drug Supply Chain Control Tower"
    )

    tasks = [sendAlert("STOCKOUT_RISK", msg, r.strip()) for r in DEFAULT_RECIPIENTS]
    await asyncio.gather(*tasks)


async def alert_anomaly(batch_id: str, rule_triggered: str, details: str) -> None:
    """Fire when a new anomaly is written to the anomalies table."""
    msg = (
        f"⚠️ ANOMALY DETECTED\n"
        f"Batch: {batch_id}\n"
        f"Rule: {rule_triggered}\n"
        f"Details: {details[:200]}\n"
        f"— Drug Supply Chain Control Tower"
    )

    tasks = [sendAlert("ANOMALY", msg, r.strip()) for r in DEFAULT_RECIPIENTS]
    await asyncio.gather(*tasks)


async def alert_expiry_risk(drug_name: str, batch_id: str, units_at_risk: float, expiry_date: str) -> None:
    """Fire when a batch is flagged as expiry risk."""
    msg = (
        f"⏰ EXPIRY RISK — {drug_name}\n"
        f"Batch: {batch_id}\n"
        f"Units at risk: {units_at_risk:.0f}\n"
        f"Expiry date: {expiry_date}\n"
        f"Consider redistribution or early dispensing.\n"
        f"— Drug Supply Chain Control Tower"
    )

    tasks = [sendAlert("EXPIRY_RISK", msg, r.strip()) for r in DEFAULT_RECIPIENTS]
    await asyncio.gather(*tasks)


# ── Supabase Realtime: listen for new anomalies ───────────────────────────────

def subscribe_anomalies_realtime() -> None:
    """
    Subscribe to Supabase Realtime INSERT events on the anomalies table.
    Fires alert_anomaly() for each new row.

    Run this in a separate thread/process or as a background task in FastAPI.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("⚠️  Supabase not configured — anomaly subscription disabled")
        return

    supabase: Client = create_client(url, key)

    def on_anomaly(payload: dict) -> None:
        record = payload.get("new", {})
        asyncio.run(alert_anomaly(
            batch_id=record.get("batch_id", "unknown"),
            rule_triggered=record.get("rule_triggered", "unknown"),
            details=record.get("details", ""),
        ))

    print("📡 Subscribed to anomalies table (Supabase Realtime)")
    (
        supabase
        .channel("anomalies-channel")
        .on("postgres_changes", {"event": "INSERT", "schema": "public", "table": "anomalies"}, on_anomaly)
        .subscribe()
    )

    # Keep alive (run in background thread)
    import time
    while True:
        time.sleep(5)


# ── check forecasts and fire stockout alerts ──────────────────────────────────

async def check_and_fire_stockout_alerts(forecast_results: list[dict]) -> None:
    """
    Given forecast results from the pipeline, fire alerts for
    drugs predicted to stock out within STOCKOUT_WARN_DAYS.
    """
    today = date.today()
    for r in forecast_results:
        stockout = r.get("predicted_stockout_date")
        if not stockout:
            continue
        days_left = (date.fromisoformat(stockout) - today).days
        if 0 < days_left <= STOCKOUT_WARN_DAYS:
            await alert_stockout_risk(
                drug_name=r.get("drug_name", r["drug_id"]),
                stockout_date=stockout,
                current_stock=r["current_stock"],
            )


# ── WhatsApp Cloud API ────────────────────────────────────────────────────────

async def _send_whatsapp(to: str, message: str) -> dict:
    """
    Send a text message via Meta WhatsApp Cloud API.
    Recipient must have opted in (WhatsApp policy requirement).
    """
    # Format: WhatsApp requires numbers without + prefix in some regions;
    # the API accepts both — we strip + to be safe
    to_clean = to.lstrip("+")

    url = f"https://graph.facebook.com/{WA_API_VERSION}/{WA_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_clean,
        "type": "text",
        "text": {"body": message},
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


# ── Twilio SMS ────────────────────────────────────────────────────────────────

async def _send_sms(to: str, message: str) -> dict:
    """Send SMS via Twilio REST API."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    data = {
        "From": TWILIO_FROM_NUMBER,
        "To": to,
        "Body": message[:1600],  # Twilio SMS limit
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, auth=auth, data=data)
        resp.raise_for_status()
        return resp.json()


# ── write to alerts table ─────────────────────────────────────────────────────

async def _write_alert_to_db(
    alert_type: str,
    message: str,
    recipient: str,
    channel: str,
    success: bool,
) -> None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return

    supabase: Client = create_client(url, key)
    try:
        supabase.table("alerts").insert({
            "type": alert_type,
            "message": message,
            "recipient": recipient,
            "channel": channel,
            "sent_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception as e:
        print(f"  ⚠️  Could not write alert to DB: {e}")


# ── standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio

    async def test():
        print("Testing sendAlert (no real credentials needed for log-only mode)\n")

        result = await sendAlert(
            alert_type="STOCKOUT_RISK",
            message="Test: Paracetamol stock critical — 3 days to stockout",
            recipient="+919999999999",
            channel="whatsapp",
        )
        print(f"Result: {result}")

    asyncio.run(test())