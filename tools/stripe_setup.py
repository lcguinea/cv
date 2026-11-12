#!/usr/bin/env python3
"""Creates or reuses the Stripe objects of the class plans, through the Stripe CLI (TEST mode only).

    stripe login                       # choose the sandbox "Luis Guinea Formacion (pruebas)"
    python3 tools/stripe_setup.py      # idempotent: prints the ids to put in the Apps Script properties

Objects (found again by lookup_key / metadata, so running it twice never duplicates anything):
    product  "Clases particulares de música · Luis Guinea"            metadata.lg_key = clases_presenciales
    price    14800 EUR, recurring week x4, lookup_key lg_clases_semanal     -> STRIPE_PRICE_WEEKLY
    price    14800 EUR, recurring week x8, lookup_key lg_clases_quincenal   -> STRIPE_PRICE_BIWEEKLY
    portal   payment method, invoices, cancel at period end (no plan changes, no pause, no prorations)
                                                                              -> STRIPE_PORTAL_CONFIG
Prices are never modified: a wrong price is reported, not changed. Live mode is refused: going live is a separate,
approved step (apps-script/BILLING.md, "Activación en real").
"""
import json
import subprocess
import sys

PRODUCT_KEY = "clases_presenciales"
PRICES = {"weekly": ("lg_clases_semanal", 4), "biweekly": ("lg_clases_quincenal", 8)}
SITE = "https://luisguinea.com/"


def stripe(*args):
    if "--live" in args:
        raise SystemExit("live mode is not allowed from this script")
    out = subprocess.run(["stripe", *args], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(out.stderr.strip() or out.stdout.strip())
    data = json.loads(out.stdout)
    if isinstance(data, dict) and data.get("error"):
        raise SystemExit(json.dumps(data["error"]))
    if isinstance(data, dict) and data.get("livemode"):
        raise SystemExit("the CLI is pointing at live mode: stop")
    return data


def find_product():
    for p in stripe("products", "list", "--limit", "100").get("data", []):
        if (p.get("metadata") or {}).get("lg_key") == PRODUCT_KEY:
            return p
    return None


def main():
    product = find_product()
    if not product:
        product = stripe("products", "create", "--name", "Clases particulares de música · Luis Guinea",
                         "--description", "Plan de 4 clases individuales presenciales de 60 minutos en Valencia.",
                         "-d", f"metadata[lg_key]={PRODUCT_KEY}",
                         "--statement-descriptor", "LUISGUINEA CLASES")
        print("created product", product["id"])
    else:
        print("reusing product", product["id"])
    ids = {}
    for plan, (lookup, weeks) in PRICES.items():
        found = stripe("prices", "list", "-d", f"lookup_keys[]={lookup}", "--limit", "1").get("data", [])
        if found:
            price = found[0]
            ok = (price["unit_amount"] == 14800 and price["currency"] == "eur" and price["recurring"]["interval"] == "week"
                  and price["recurring"]["interval_count"] == weeks and price["active"] and price["product"] == product["id"])
            print(("reusing" if ok else "WRONG, not modified:"), plan, price["id"])
            if not ok:
                return 1
        else:
            price = stripe("prices", "create", "--product", product["id"], "--currency", "eur", "--unit-amount", "14800",
                           "-d", "recurring[interval]=week", "-d", f"recurring[interval_count]={weeks}",
                           "-d", "tax_behavior=inclusive", "--lookup-key", lookup,
                           "--nickname", f"Plan {'semanal' if plan == 'weekly' else 'quincenal'} · 4 clases")
            print("created price", plan, price["id"])
        ids[plan] = price["id"]

    portal = None
    for c in stripe("get", "/v1/billing_portal/configurations", "-d", "limit=100").get("data", []):
        if (c.get("metadata") or {}).get("lg_key") == PRODUCT_KEY and c.get("active"):
            portal = c
    if not portal:
        portal = stripe(
            "post", "/v1/billing_portal/configurations",
            "-d", "metadata[lg_key]=" + PRODUCT_KEY,
            "-d", "business_profile[headline]=Clases de música con Luis Guinea",
            "-d", f"business_profile[privacy_policy_url]={SITE}formacion/#planes",
            "-d", f"business_profile[terms_of_service_url]={SITE}formacion/#planes",
            "-d", f"default_return_url={SITE}alumnos/",
            "-d", "features[invoice_history][enabled]=true",
            "-d", "features[payment_method_update][enabled]=true",
            "-d", "features[customer_update][enabled]=false",
            "-d", "features[subscription_cancel][enabled]=true",
            "-d", "features[subscription_cancel][mode]=at_period_end",
            "-d", "features[subscription_cancel][proration_behavior]=none",
            "-d", "features[subscription_cancel][cancellation_reason][enabled]=true",
            "-d", "features[subscription_cancel][cancellation_reason][options][]=too_expensive",
            "-d", "features[subscription_cancel][cancellation_reason][options][]=unused",
            "-d", "features[subscription_cancel][cancellation_reason][options][]=other",
            "-d", "features[subscription_update][enabled]=false",
        )
        print("created portal configuration", portal["id"])
    else:
        print("reusing portal configuration", portal["id"])
    print("\nScript Properties (test):")
    print("  STRIPE_MODE           = test")
    print("  STRIPE_PRICE_WEEKLY   =", ids["weekly"])
    print("  STRIPE_PRICE_BIWEEKLY =", ids["biweekly"])
    print("  STRIPE_PORTAL_CONFIG  =", portal["id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
