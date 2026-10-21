#!/usr/bin/env python3
"""Focused tests for the booking system (apps-script/Code.gs, agenda/index.html, js/agenda.js).

The Apps Script runs in Node's vm with Google services replaced by mocks (tests/support/reservas_scenarios.js):
availability, 30/60/120/180 minute durations, Europe/Madrid and daylight saving, notice and horizon limits,
buffers, conflicts without leaking private details, email verification before any invitation, virtual (Google
Meet) and in-person (no conference, place to be agreed) meetings, duplicates,
simultaneous requests, idempotent retries, rate limits, CacheService limits, Google Meet states and strict
validation. Static checks cover the page, the integration rules and that no secret or iframe is shipped.

Node is required: without it these tests fail instead of being skipped, so a green run always means the
scenarios really ran. Run: python3 -m unittest tests/test_reservas.py
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
SCENARIOS = ROOT / "tests" / "support" / "reservas_scenarios.js"
# The deployed web app URL is public (every visitor's browser calls it), not a credential. Same shape as
# ENDPOINT_RE in js/agenda.js; empty means "not deployed yet".
ENDPOINT_ATTR = re.compile(r'data-endpoint="(?:https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec)?"')


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class AppsScriptLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not NODE:
            raise AssertionError("node is required for the booking tests (tests/support/reservas_scenarios.js); install Node.js")
        run = subprocess.run([NODE, str(SCENARIOS)], capture_output=True, text=True, timeout=120)
        if run.returncode != 0:
            raise AssertionError(run.stderr)
        cls.results = json.loads(run.stdout)

    def test_every_scenario_passes(self):
        self.assertGreaterEqual(len(self.results), 47)
        for name, outcome in self.results.items():
            with self.subTest(scenario=name):
                self.assertEqual(outcome, "ok")

    def test_required_areas_are_covered(self):
        names = " ".join(self.results)
        for area in ("durations_30_60_120_180_book_and_confirm", "dst_autumn", "dst_spring", "buffer", "min_notice", "conflicts",
                     "private_event", "invitation_is_never_sent_before_the_email_is_verified", "forged_token", "expires",
                     "duplicate", "simultaneous", "rechecked_inside_the_lock", "retry_with_the_same_request_id",
                     "lost_calendar_response", "validation", "rate_limits_failed_or_invalid_requests_never_block",
                     "pending_holds_are_capped", "too_big_for_the_cache", "disappears_from_every_cached_listing",
                     "meet_link_is_only_reported_once_it_exists", "meet_failure",
                     "virtual_booking_keeps_meet_and_carries_modality_and_reason",
                     "in_person_booking_sends_invitation_without_any_conference", "in_person_in_spanish_says_the_place_is_pending",
                     "in_person_and_virtual_share_availability_holds_and_expiry"):
            self.assertIn(area, names)


class IntegrationTests(unittest.TestCase):
    def test_page_and_access_exist(self):
        html = read("agenda/index.html")
        self.assertIn('rel="canonical" href="https://luisguinea.com/agenda/"', html)
        self.assertIn('href="agenda/"', read("index.html"))
        self.assertIn("https://luisguinea.com/agenda/", read("sitemap.xml"))
        self.assertIn('<a href="../music/" data-section="music"', html)  # header link leaves /agenda/
        self.assertIn("agenda/index.html", read("tools/build_site.py"))
        self.assertIn("js/agenda.js", read("tools/build_site.py"))

    def test_no_iframe_anywhere_in_published_files(self):
        for rel in ("index.html", "cv.html", "music/index.html", "sobre-mi.html", "404.html", "agenda/index.html", "js/agenda.js"):
            self.assertNotRegex(read(rel).lower(), r"<iframe|\.createelement\(.iframe", rel)

    def test_frontend_is_safe(self):
        js = read("js/agenda.js")
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("eval(", js)
        self.assertIn("credentials: 'omit'", js)
        self.assertIn("text/plain", js)  # simple request: no preflight, no CORS workaround
        self.assertIn("script\\.google\\.com\\/macros\\/s\\/", js)
        self.assertNotIn("mode: 'no-cors'", js)
        self.assertEqual(len(re.findall(r'data-endpoint="', read("agenda/index.html"))), 1)
        self.assertRegex(read("agenda/index.html"), ENDPOINT_ATTR)
        # Retries reuse one request id; the confirmation token comes in the fragment and is removed from the URL.
        self.assertIn("requestId: requestIdFor(payload)", js)
        self.assertIn("history.replaceState", js)
        self.assertIn("#confirm=", js)
        # A Meet link is only shown when the backend reports one that exists.
        self.assertIn("meet.status === 'ready'", js)
        self.assertIn("MEET_RE.test(meet.link)", js)
        self.assertNotIn("meetLink", js)
        # Format and reason travel with the booking; Virtual is the initial, required choice.
        self.assertIn("modality: modality()", js)
        self.assertIn("reason: $('agenda-reason').value.trim()", js)
        html = read("agenda/index.html")
        self.assertIn('<input type="radio" name="modality" value="virtual" checked required>', html)
        self.assertIn('<input type="radio" name="modality" value="in_person" required>', html)
        self.assertIn('<input id="agenda-reason" name="reason" type="text" maxlength="150"', html)
        # The agenda's display rules (e.g. links as inline-flex) must not reveal a hidden Meet link.
        self.assertIn(".agenda-app [hidden]{display:none!important}", read("css/styles.css"))

    def test_backend_rules(self):
        gs = read("apps-script/Code.gs")
        self.assertIn("LockService.getScriptLock()", gs)
        for fn in ("function requestBooking_", "function confirmBooking_"):
            body = gs[gs.index(fn):]
            self.assertTrue(body.split("\n", 1)[1].lstrip().startswith("return withLock_("), fn)
        self.assertLess(gs.index("function requestBooking_"), gs.index("slotsFor_(cfg, req.durationMin"))
        # Invitations: one place only, after the token check; the hold sends nothing and has no attendees.
        self.assertEqual(gs.count("sendUpdates: 'all'"), 1)
        self.assertGreater(gs.index("sendUpdates: 'all'"), gs.index("function confirmBooking_"))
        hold = gs[gs.index("function insertHold_"):gs.index("function sendConfirmation_")]
        self.assertNotIn("attendees", hold)
        self.assertIn("sendUpdates: 'none'", hold)
        # Meet is requested only for virtual meetings: in person, the patch carries no conference data.
        confirm = gs[gs.index("function confirmBooking_"):gs.index("function refreshMeet_")]
        self.assertEqual(gs.count("hangoutsMeet"), 1)
        self.assertEqual(gs.count("conferenceDataVersion = 1"), 1)
        guard = confirm.index("if (virtual) {")
        self.assertLess(guard, confirm.index("patch.conferenceData ="))
        self.assertLess(guard, confirm.index("options.conferenceDataVersion = 1"))
        self.assertIn("var virtual = rec.modality !== 'in_person';", confirm)
        self.assertIn("Calendar.Freebusy.query", gs)
        self.assertNotRegex(gs, r"getTitle|getDescription|getGuestList|\.summary\b.*busy")
        self.assertIn("Europe/Madrid", gs)

    def test_no_secrets_or_real_identifiers(self):
        pattern = re.compile(r"AKfycb[\w-]{20,}|AIza[\w-]{30,}|-----BEGIN|client_secret|[\w-]{20,}@group\.calendar\.google\.com|ya29\.")
        for rel in ("apps-script/Code.gs", "apps-script/README.md", "apps-script/appsscript.json", "agenda/index.html", "js/agenda.js"):
            # Only the public endpoint attribute is exempt; the same id anywhere else is still flagged.
            self.assertIsNone(pattern.search(ENDPOINT_ATTR.sub('data-endpoint=""', read(rel))), rel)

    def test_manifest_requests_only_needed_scopes(self):
        manifest = json.loads(read("apps-script/appsscript.json"))
        self.assertEqual(manifest["timeZone"], "Europe/Madrid")
        self.assertEqual(manifest["webapp"]["access"], "ANYONE_ANONYMOUS")
        self.assertEqual(manifest["webapp"]["executeAs"], "USER_DEPLOYING")
        self.assertEqual(sorted(manifest["oauthScopes"]), ["https://www.googleapis.com/auth/calendar",
                                                           "https://www.googleapis.com/auth/script.send_mail"])
        services = [s["serviceId"] for s in manifest["dependencies"]["enabledAdvancedServices"]]
        self.assertEqual(services, ["calendar"])

    def test_documentation_covers_manual_setup(self):
        doc = read("apps-script/README.md")
        for needle in ("AVAILABILITY_CALENDAR_ID", "BOOKING_CALENDAR_ID", "BUSY_CALENDAR_IDS", "CONFIRM_URL", "HOLD_MINUTES",
                       "MAX_PENDING_HOLDS", "Calendar API", "script.send_mail", "sweepExpiredHolds", "Deploy",
                       "data-endpoint", "HTML Service", "LockService", "CORS", "modality", "in_person", "reason"):
            self.assertIn(needle, doc)


if __name__ == "__main__":
    unittest.main()
