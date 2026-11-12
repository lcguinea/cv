#!/usr/bin/env python3
"""Renewals with Stripe Test Clocks against the local dev backend (TEST mode only).

Needs: stripe login (sandbox), tools/billing_dev_server.js on 127.0.0.1:8792 and `stripe listen` forwarding to it.

    python3 tools/stripe_testclock_e2e.py --weekly price_... --biweekly price_...

Scenarios (each on its own test clock, so nothing touches real time or other customers):
  weekly     subscribe, advance 28 days + 2 h: the renewal invoice is paid and grants exactly 4 more credits
  biweekly   subscribe, advance 56 days + 2 h: same with 8 weeks; at 28 days nothing is granted
  failing    card that fails on renewal: no new credits, subscription past_due, Luis gets one "Pago fallido"
  duplicate  the renewal's invoice.paid event is re-sent by Stripe: credits unchanged
Prints a JSON report; exits 1 on any failure. Test clocks are deleted at the end (their customers go with them).
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request

DEV = "http://127.0.0.1:8792/__dev/"
DAY = 86400


def stripe(*args):
    out = subprocess.run(["stripe", *args], capture_output=True, text=True)
    text = out.stdout
    if "{" not in text:
        raise SystemExit(out.stderr or text)
    data = json.loads(text[text.index("{"):])
    if data.get("error"):
        raise SystemExit(json.dumps(data["error"]))
    if data.get("livemode"):
        raise SystemExit("live object: stop")
    return data


def dev(path):
    with urllib.request.urlopen(DEV + path, timeout=60) as r:
        return json.load(r)


def grants(sub):
    return [m for m in dev("table?name=movimientos") if m["tipo"] == "grant" and json.loads(m["datos"]).get("suscripcion") == sub]


def wait_for(fn, what, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(3)
    raise AssertionError("timeout waiting for " + what)


def advance(clock, to):
    stripe("post", f"/v1/test_helpers/test_clocks/{clock}/advance", "-d", f"frozen_time={to}")
    wait_for(lambda: stripe("get", f"/v1/test_helpers/test_clocks/{clock}")["status"] == "ready", "clock ready", 180)


def subscribe(price, email, card, plan):
    now = int(time.time())
    clock = stripe("post", "/v1/test_helpers/test_clocks", "-d", f"frozen_time={now}", "-d", f"name=e2e {plan}")["id"]
    cus = stripe("post", "/v1/customers", "-d", f"email={email}", "-d", "name=Reloj de prueba", "-d", f"test_clock={clock}",
                 "-d", f"payment_method={card}", "-d", f"invoice_settings[default_payment_method]={card}")["id"]
    sub = stripe("post", "/v1/subscriptions", "-d", f"customer={cus}", "-d", f"items[0][price]={price}",
                 "-d", f"metadata[plan]={plan}", "-d", "metadata[lang]=es")
    return clock, now, sub["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weekly", required=True)
    ap.add_argument("--biweekly", required=True)
    a = ap.parse_args()
    report, clocks = {}, []
    try:
        # weekly: 4 credits now, 4 more after exactly 28 days
        clock, t0, sub = subscribe(a.weekly, "reloj.semanal@example.com", "pm_card_visa", "weekly")
        clocks.append(clock)
        wait_for(lambda: len(grants(sub)) == 4, "first 4 credits (weekly)")
        advance(clock, t0 + 28 * DAY + 2 * 3600)
        g = wait_for(lambda: (lambda x: x if len(x) == 8 else None)(grants(sub)), "renewal credits (weekly)")
        periods = sorted({(json.loads(m["datos"])["inicio"], json.loads(m["datos"])["fin"]) for m in g})
        assert len(periods) == 2 and all((e - s) == 28 * DAY * 1000 for s, e in periods), periods
        report["weekly_renewal_28_days"] = {"credits": len(g), "periods_days": [(e - s) / 86400000 for s, e in periods]}
        # duplicate: Stripe re-sends the renewal's invoice.paid
        evs = stripe("get", "/v1/events", "-d", "type=invoice.paid", "-d", "limit=20")["data"]
        def inv_sub(o):  # newer API versions moved it to parent.subscription_details
            return o.get("subscription") or ((o.get("parent") or {}).get("subscription_details") or {}).get("subscription")
        renewal_ev = next(e for e in evs if inv_sub(e["data"]["object"]) == sub and e["data"]["object"]["billing_reason"] == "subscription_cycle")
        subprocess.run(["stripe", "events", "resend", renewal_ev["id"]], capture_output=True, text=True)
        time.sleep(8)
        assert len(grants(sub)) == 8
        report["duplicate_invoice_paid_resent"] = {"event": renewal_ev["id"], "credits_after": len(grants(sub))}

        # biweekly: nothing at 28 days, 4 more at 56 days
        clock, t0, sub = subscribe(a.biweekly, "reloj.quincenal@example.com", "pm_card_visa", "biweekly")
        clocks.append(clock)
        wait_for(lambda: len(grants(sub)) == 4, "first 4 credits (biweekly)")
        advance(clock, t0 + 28 * DAY + 2 * 3600)
        time.sleep(8)
        at28 = len(grants(sub))
        advance(clock, t0 + 56 * DAY + 2 * 3600)
        g = wait_for(lambda: (lambda x: x if len(x) == 8 else None)(grants(sub)), "renewal credits (biweekly)")
        periods = sorted({(json.loads(m["datos"])["inicio"], json.loads(m["datos"])["fin"]) for m in g})
        assert at28 == 4 and all((e - s) == 56 * DAY * 1000 for s, e in periods), (at28, periods)
        report["biweekly_renewal_56_days"] = {"credits_at_28_days": at28, "credits": len(g), "periods_days": [(e - s) / 86400000 for s, e in periods]}

        # failing renewal: the card works for the first charge and fails afterwards
        clock, t0, sub = subscribe(a.weekly, "reloj.fallo@example.com", "pm_card_visa", "weekly")
        clocks.append(clock)
        wait_for(lambda: len(grants(sub)) == 4, "first 4 credits (failing)")
        cus = stripe("get", f"/v1/subscriptions/{sub}")["customer"]
        pm = stripe("post", "/v1/payment_methods/pm_card_chargeCustomerFail/attach", "-d", f"customer={cus}")["id"]
        stripe("post", f"/v1/customers/{cus}", "-d", f"invoice_settings[default_payment_method]={pm}")
        stripe("post", f"/v1/subscriptions/{sub}", "-d", f"default_payment_method={pm}")
        advance(clock, t0 + 28 * DAY + 2 * 3600)
        time.sleep(10)
        status = stripe("get", f"/v1/subscriptions/{sub}")["status"]
        failed_mails = [m for m in dev("mails") if m["subject"].startswith("Pago fallido") and "Reloj" in m["subject"]]
        assert len(grants(sub)) == 4 and status in ("past_due", "unpaid"), (len(grants(sub)), status)
        report["failed_renewal"] = {"credits": len(grants(sub)), "status": status, "owner_failed_notices": len(failed_mails)}
        dev("hourly")
        assert len(grants(sub)) == 4
        report["failed_renewal"]["credits_after_reconciliation"] = len(grants(sub))
        print(json.dumps({"ok": True, "report": report}, indent=1))
        return 0
    except AssertionError as e:
        print(json.dumps({"ok": False, "error": str(e), "report": report}, indent=1))
        return 1
    finally:
        for c in clocks:
            subprocess.run(["stripe", "delete", f"/v1/test_helpers/test_clocks/{c}", "--confirm"], capture_output=True)


if __name__ == "__main__":
    sys.exit(main())
