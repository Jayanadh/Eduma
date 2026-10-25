"""A defined read workload (BUILD-12): concurrent clients, each signed in as a demo persona, repeat that persona's
everyday reads against the current database; prints p50/p95 per request and compares p95 with the pack's planning
target (800 ms for ordinary reads). In-process (Django's test client), so it measures the application and database,
not the network or a production web server. Run on seeded demo data: manage.py measure_workload --clients 8 --rounds 20
"""

import statistics
import threading
import time
from collections import defaultdict
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test import Client

from accounts.models import User
from institutions.models import Institution

TARGET_MS = 800
WORKLOAD = [
    ("aster", "aster.admin", "/api/v1/session"),
    ("aster", "aster.admin", "/api/v1/institution/students?search=demo"),
    ("aster", "aster.admin", "/api/v1/institution/staff"),
    ("aster", "aster.principal", "/api/v1/institution/reports/students_by_class"),
    ("aster", "aster.accountant", "/api/v1/institution/fees/trial-balance"),
    ("aster", "aster.teacher", "/api/v1/teaching/classes"),
    ("aster", "aster.teacher", "/api/v1/communication/conversations"),
    ("aster", "aster.teacher", "/api/v1/service-cases/"),
    ("aster", "aster.parent", "/api/v1/family/children"),
    ("aster", "aster.2027-0001", "/api/v1/student/me"),
    ("aster", "aster.hr", "/api/v1/institution/hr/leave?all=1"),
    ("aster", "aster.stores", "/api/v1/institution/stores/requisitions"),
    ("meridian", "meridian.2026-0001", "/api/v1/student/registration"),
]


class Command(BaseCommand):
    help = "Measure p50/p95 of everyday reads under concurrent demo personas."

    def add_arguments(self, parser):
        parser.add_argument("--clients", type=int, default=8)
        parser.add_argument("--rounds", type=int, default=20)

    def handle(self, *args, **options):
        users = {u.username: u for u in User.objects.filter(username__in={w[1] for w in WORKLOAD})}
        missing = {w[1] for w in WORKLOAD} - set(users)
        if missing:
            raise CommandError(f"Seed the demo data first (missing {', '.join(sorted(missing))}).")
        base = urlparse(settings.EDUMA_BASE_URL).hostname  # localhost in development
        sites = {i.slug: str(i.id) for i in Institution.objects.filter(slug__in={w[0] for w in WORKLOAD})}
        timings, failures, lock = defaultdict(list), defaultdict(int), threading.Lock()

        crashed = []

        def client_loop():
            try:
                run_client()
            except Exception as error:  # a crashed client is reported, not silently dropped
                crashed.append(repr(error))
            finally:
                connection.close()

        def run_client():
            clients = {}
            for slug, username, _ in WORKLOAD:
                if username not in clients:
                    c = Client(HTTP_HOST=f"{slug}.{base}")
                    c.force_login(users[username])
                    session = c.session  # sessions belong to the site they were made on, as a real sign-in sets
                    session["site"] = sites[slug]
                    session.save()
                    clients[username] = c
            for _ in range(options["rounds"]):
                for slug, username, path in WORKLOAD:
                    start = time.perf_counter()
                    response = clients[username].get(path)
                    ms = (time.perf_counter() - start) * 1000
                    with lock:
                        timings[path].append(ms)
                        failures[path] += response.status_code >= 400

        threads = [threading.Thread(target=client_loop) for _ in range(options["clients"])]
        began = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        took = time.perf_counter() - began
        total = sum(len(v) for v in timings.values())
        self.stdout.write(
            f"{options['clients']} clients x {options['rounds']} rounds: {total} requests in {took:.1f} s"
        )
        if crashed:
            raise CommandError(f"{len(crashed)} client(s) failed: {crashed[0]}")
        worst = 0.0
        for _, _, path in WORKLOAD:
            values = sorted(timings[path])
            p95 = values[max(0, int(len(values) * 0.95) - 1)]
            worst = max(worst, p95)
            self.stdout.write(
                f"  p50 {statistics.median(values):7.1f} ms  p95 {p95:7.1f} ms  errors {failures[path]}  {path}"
            )
        verdict = "within" if worst < TARGET_MS else "OVER"
        self.stdout.write(f"Worst p95 {worst:.1f} ms: {verdict} the {TARGET_MS} ms planning target for reads.")
