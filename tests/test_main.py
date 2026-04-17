import unittest

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class FastAPITestCase(unittest.TestCase):
    def test_apidocs(self):
        response = client.get("/docs")
        self.assertEqual(response.status_code, 200)

    def test_openapi(self):
        response = client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
