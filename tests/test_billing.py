#!/usr/bin/env python3
"""Tests for the class subscriptions (mission 04): apps-script/Billing.gs, workers/stripe-relay/worker.js, the plans
section and the student area.

- tests/support/billing_scenarios.js runs Code.gs + Billing.gs with mocked Google services and an in-memory Stripe:
  checkout of both plans, confirmed and declined payments, 4- and 8-week renewals, duplicated and out-of-order
  webhooks, cancellations, 24-hour rule, simultaneous requests, carry-over and its limits, deadlines, backend failures,
  retries, status queries, access control, reconciliation, refunds, teacher cancellations and the general agenda.
- tests/support/stripe_relay_scenarios.mjs checks the Stripe signature handling of the relay.
- Static checks: nothing is published until approved, no secret in the repository, Stripe ids are never credentials.

Node is required (the tests fail without it). Run: python3 -m unittest tests/test_billing.py
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
sys.path.insert(0, str(ROOT / "tools"))
import formacion_content  # noqa: E402


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def run_node(script):
    if not NODE:
        raise AssertionError("node is required for the billing tests")
    run = subprocess.run([NODE, str(ROOT / script)], capture_output=True, text=True, timeout=300, cwd=ROOT)
    if run.returncode != 0:
        raise AssertionError(run.stderr)
    return json.loads(run.stdout)


class BillingScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = run_node("tests/support/billing_scenarios.js")

    def test_every_scenario_passes(self):
        self.assertGreaterEqual(len(self.results), 34)
        for name, outcome in self.results.items():
            with self.subTest(scenario=name):
                self.assertEqual(outcome, "ok")

    def test_the_twenty_required_cases_are_covered(self):
        names = " ".join(self.results)
        for case in ("weekly_plan", "biweekly_plan", "declined_card", "renewal_after_four_weeks", "renewal_after_eight_weeks",
                     "duplicate_webhooks", "out_of_order", "cancellation_at_period_end", "immediate_cancellation",
                     "reschedules_with_notice", "inside_twenty_four_hours", "simultaneous_requests", "one_or_two_unused_credits",
                     "at_most_two_credits", "recovery_deadline", "keeps_paid_credits", "temporary_backend_failure",
                     "retried_requests", "once_payment_is_confirmed", "nobody_reaches_another_students_data"):
            # case 19 (status query) is checked in weekly_plan_..._once_payment_is_confirmed and in several views
            self.assertTrue(case in names, case)


class RelayScenarios(unittest.TestCase):
    def test_every_relay_scenario_passes(self):
        results = run_node("tests/support/stripe_relay_scenarios.mjs")
        self.assertGreaterEqual(len(results), 9)
        for name, outcome in results.items():
            with self.subTest(scenario=name):
                self.assertEqual(outcome, "ok")


class PublishedWithTheLiveBackend(unittest.TestCase):
    """Launched on 2026-11-13 (Mission 06) with the signed checklist: the plans are public and call the production
    Apps Script; nothing of the test environment may leak into the published pages."""
    LIVE = "https://script.google.com/macros/s/AKfycbxj7SKKv5Pn4zb3oyqC8w3K8F3Ye4Zs4EHaUeBVvV3nIrBxbKvzBg8csvQhbXWpprpe/exec"

    def test_flag_is_on_with_the_production_endpoint(self):
        self.assertTrue(formacion_content.SUBSCRIPTIONS["published"])
        self.assertEqual(formacion_content.SUBSCRIPTIONS["endpoint"], self.LIVE)

    def test_generated_pages_carry_the_plans_and_no_test_identifiers(self):
        hub = read("formacion/index.html")
        self.assertIn('id="planes"', hub)
        self.assertIn("plans.js", hub)
        self.assertIn(f'data-endpoint="{self.LIVE}"', hub)
        self.assertTrue((ROOT / "alumnos" / "index.html").exists())
        self.assertTrue((ROOT / "formacion" / "condiciones" / "index.html").exists())
        for page in ("formacion/index.html", "alumnos/index.html", "formacion/condiciones/index.html", "js/learn-strings.js"):
            text = read(page)
            self.assertNotRegex(text, r"127\.0\.0\.1|cs_test_|pk_test_|sk_test_|rk_test_|price_1Ub0", page)

    def test_site_artifact_includes_them_and_nothing_private(self):
        with tempfile.TemporaryDirectory() as out:
            subprocess.run([sys.executable, str(ROOT / "tools" / "build_site.py"), "--out", out], check=True, capture_output=True)
            files = {str(p.relative_to(out)) for p in Path(out).rglob("*") if p.is_file()}
        for rel in ("alumnos/index.html", "js/plans.js", "js/alumnos.js", "formacion/condiciones/index.html"):
            self.assertIn(rel, files)
        self.assertFalse(any(f.startswith(("apps-script/", "workers/", "tools/", "docs/", "tests/")) for f in files))

    def test_preview_builds_outside_the_repository_only(self):
        with tempfile.TemporaryDirectory() as out:
            run = subprocess.run([sys.executable, str(ROOT / "tools" / "build_formacion.py"), "--preview",
                                  "http://127.0.0.1:8792/exec", "--out", out], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            hub = (Path(out) / "formacion" / "index.html").read_text(encoding="utf-8")
            students = (Path(out) / "alumnos" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="planes"', hub)
        self.assertIn('name="plan" value="weekly"', hub)
        self.assertIn('name="plan" value="biweekly"', hub)
        self.assertIn('href="../alumnos/"', hub)
        self.assertIn("cada 4 semanas", hub)
        self.assertIn("cada 8 semanas", hub)
        self.assertIn('content="noindex,nofollow"', students)
        self.assertIn('href="../formacion/" data-section="lessons"', students)
        self.assertNotIn("—", hub + students)
        refused = subprocess.run([sys.executable, str(ROOT / "tools" / "build_formacion.py"), "--preview", "x", "--out", str(ROOT / "tmp")],
                                 capture_output=True, text=True)
        self.assertNotEqual(refused.returncode, 0)


class SecurityStatics(unittest.TestCase):
    FILES = ("apps-script/Billing.gs", "apps-script/Code.gs", "workers/stripe-relay/worker.js", "workers/stripe-relay/wrangler.toml",
             "js/plans.js", "js/alumnos.js", "tools/billing_dev_server.js", "tools/stripe_setup.py", "tools/stripe_testclock_e2e.py", "tools/formacion_content.py",
             "apps-script/BILLING.md")
    SECRET = re.compile(r"(?:sk|rk)_(?:test|live)_[A-Za-z0-9]{12,}|whsec_[A-Za-z0-9]{20,}|pk_live_[A-Za-z0-9]{12,}")

    def test_no_secret_in_the_repository(self):
        for rel in self.FILES:
            with self.subTest(rel):
                self.assertIsNone(self.SECRET.search(read(rel)), rel)

    def test_browser_code_never_grants_or_trusts_payment(self):
        js = read("js/plans.js") + read("js/alumnos.js")
        self.assertNotIn("api.stripe.com", js)
        self.assertNotIn("innerHTML", read("js/alumnos.js"))
        self.assertIn("history.replaceState", read("js/alumnos.js"))  # tokens leave the address bar
        for host in (r"checkout\.stripe\.com", r"billing\.stripe\.com"):
            self.assertTrue(host in js, host)  # only Stripe-hosted pages are opened

    def test_backend_rules(self):
        gs = read("apps-script/Billing.gs")
        self.assertIn("'grant:' + inv.id + ':' + n", gs)  # one grant id per invoice and credit: never twice
        self.assertIn("inv.status !== 'paid'", gs)
        self.assertIn("withLock_", gs)
        self.assertIn("stripe_(bcfg, 'get', '/events/'", gs)  # events are downloaded again from Stripe
        self.assertIn("keyMode !== mode", gs)  # a live key never runs in test mode and vice versa
        self.assertNotRegex(gs, r"trial_period|coupon|discounts")

    def test_terms_version_matches_the_published_page(self):
        version = re.search(r"var TERMS_VERSION = '([^']+)'", read("apps-script/Billing.gs")).group(1)
        self.assertEqual(version, formacion_content.LEGAL_VERSION)

    def test_relay_does_not_forward_payloads(self):
        worker = read("workers/stripe-relay/worker.js")
        self.assertIn("verifyStripeSignature", worker)
        self.assertIn("TOLERANCE_SECONDS = 300", worker)
        self.assertNotIn("console.log", worker)


if __name__ == "__main__":
    unittest.main()
