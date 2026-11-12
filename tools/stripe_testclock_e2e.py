#!/usr/bin/env python3
"""Renewals with Stripe Test Clocks against the local dev backend (TEST mode only).

Needs: stripe login (sandbox), tools/billing_dev_server.js on 127.0.0.1:8792 and `stripe listen` forwarding to it.

    python3 tools/stripe_testclock_e2e.py --weekly price_... --biweekly price_...

Scenarios (each on its own test clock, so nothing touches real time or other customers):
  weekly     subscribe, advance 28 days + 2 h: the renewal invoice is paid and grants exactly 4 more credits
  biweekly   subscribe, advance 56 days + 2 h: same with 8 weeks; at 28 days nothing is granted
  failing    card that fails on renewal: no new credits, subscription past_due, Luis gets one "Pago fallido"
  duplicate  the renewal's invoice.paid event is re-sent by Stripe: credits unchanged
  planchange the student switches weekly -> every two weeks from the student area (op stu_plan): nothing is charged
             now; at day 28 Stripe charges one 148 EUR invoice with no proration and the new 56-day cycle gets 4 credits
  refunds    a partial (37 EUR) and then a total refund made in Stripe: recorded in the ledger, no credit removed
  outage     webhooks fail while a renewal happens (simulated backend outage): the hourly reconciliation grants it
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
    # Same API version as apps-script/Billing.gs (STRIPE_VERSION), so the field names match the backend's.
    out = subprocess.run(["stripe", *args, "--stripe-version", "2024-06-20"], capture_output=True, text=True)
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


def post(body):
    req = urllib.request.Request("http://127.0.0.1:8792/exec", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "text/plain"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def session_for(email):
    mail = wait_for(lambda: [m for m in dev("mails") if m["to"] == email and "#acceso=" in m["body"]], "access mail for " + email)[-1]
    token = mail["body"].split("#acceso=")[1].split()[0]
    r = post({"op": "stu_login", "token": token})
    assert r.get("ok"), r
    return r["session"]


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
    ap.add_argument("--only-outage", action="store_true", help="run only the outage scenario")
    a = ap.parse_args()
    report, clocks = {}, []
    try:
        if not a.only_outage:
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
            # plan change from the student area, verified at the renewal
            clock, t0, sub = subscribe(a.weekly, "reloj.cambio@example.com", "pm_card_visa", "weekly")
            clocks.append(clock)
            wait_for(lambda: len(grants(sub)) == 4, "first 4 credits (plan change)")
            token = session_for("reloj.cambio@example.com")
            v = post({"op": "stu_plan", "token": token, "plan": "biweekly", "confirm": True})
            assert v.get("ok") and v["plan"]["pendingPlan"] == "biweekly", v
            invs_now = stripe("get", "/v1/invoices", "-d", f"subscription={sub}")["data"]
            upcoming = stripe("get", "/v1/invoices/upcoming", "-d", f"subscription={sub}")
            advance(clock, t0 + 28 * DAY + 2 * 3600)
            g = wait_for(lambda: (lambda x: x if len(x) == 8 else None)(grants(sub)), "plan change credits")
            invs = stripe("get", "/v1/invoices", "-d", f"subscription={sub}")["data"]
            lines = [(i["billing_reason"], i["amount_paid"], [l["proration"] for l in i["lines"]["data"]]) for i in invs]
            new_cycle = [json.loads(m["datos"]) for m in g if json.loads(m["datos"])["plan"] == "biweekly"]
            incidents = [i for i in dev("table?name=incidencias") if "factura" in i["detalle"] and sub in json.dumps(i)]
            assert len(invs_now) == 1 and len(invs) == 2 and all(not any(p) for _, _, p in lines) and all(x[1] == 14800 for x in lines), lines
            assert len(new_cycle) == 4 and new_cycle[0]["fin"] - new_cycle[0]["inicio"] == 56 * DAY * 1000
            report["plan_change_at_renewal"] = {"invoices_right_after_change": len(invs_now), "upcoming_amount_preview": upcoming.get("amount_due"),
                                                "invoices": lines, "new_cycle_days": (new_cycle[0]["fin"] - new_cycle[0]["inicio"]) / 86400000,
                                                "credits": len(g), "incidents": len(incidents)}

            # refunds: partial then total, on the first invoice of the plan-change customer
            first_inv = [i for i in invs if i["billing_reason"] == "subscription_create"][0]
            charge = first_inv.get("charge") or stripe("get", f"/v1/invoices/{first_inv['id']}", "-d", "expand[]=charge")["charge"]
            charge = charge["id"] if isinstance(charge, dict) else charge
            stripe("post", "/v1/refunds", "-d", f"charge={charge}", "-d", "amount=3700")
            wait_for(lambda: [m for m in dev("table?name=movimientos") if m["tipo"] == "refund" and charge in m["datos"]], "partial refund recorded")
            stripe("post", "/v1/refunds", "-d", f"charge={charge}")
            refunds = wait_for(lambda: (lambda x: x if len(x) == 2 else None)(
                [json.loads(m["datos"]) for m in dev("table?name=movimientos") if m["tipo"] == "refund" and charge in m["datos"]]), "total refund recorded")
            assert len(grants(sub)) == 8 and not [m for m in dev("table?name=movimientos") if m["tipo"] == "void"]
            report["refunds"] = {"recorded": [(r["reembolsado"], r["total"]) for r in refunds], "credits_after": len(grants(sub))}

        # outage: webhooks fail during a renewal; the hourly reconciliation recovers it
        clock, t0, sub = subscribe(a.weekly, "reloj.caida@example.com", "pm_card_visa", "weekly")
        clocks.append(clock)
        wait_for(lambda: len(grants(sub)) == 4, "first 4 credits (outage)")
        dev("outage?on=1")
        try:
            advance(clock, t0 + 28 * DAY + 2 * 3600)
            time.sleep(10)
            during = len(grants(sub))
        finally:
            dev("outage?on=0")
        dev("hourly")
        after = len(grants(sub))
        assert during == 4 and after == 8, (during, after)
        report["lost_events_recovered"] = {"credits_during_outage": during, "credits_after_hourly": after}
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
