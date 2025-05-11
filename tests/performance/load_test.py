"""Locust performance test for the CaptiveClone web interface.

Run with:
    locust -f tests/performance/load_test.py --host http://127.0.0.1:5000

The test asserts that 95% of requests complete under 200 ms.
"""
from locust import HttpUser, task, between


class CaptiveCloneUser(HttpUser):
    wait_time = between(1, 3)

    @task(5)
    def index(self):
        with self.client.get("/", catch_response=True) as resp:
            if resp.elapsed.total_seconds() > 0.2:
                resp.failure("Response time >200 ms")

    @task(2)
    def dashboard(self):
        # Requires authentication; expecting redirect to login.
        self.client.get("/dashboard", allow_redirects=True) 