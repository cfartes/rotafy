"""Verify documentation against the actual app without running its lifespan."""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.generate_integration_docs import PATHS, create_app


class IntegrationDocsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = ROOT / "docs" / "integracao"
        cls.spec = json.loads(
            (cls.directory / "openapi.json").read_text(encoding="utf-8")
        )
        cls.examples = json.loads(
            (cls.directory / "exemplos.json").read_text(encoding="utf-8")
        )

    def test_routes_and_request_schemas_exist_in_the_application(self):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            actual = create_app().openapi()
        self.assertEqual(set(self.spec["paths"]), {"/api/v1" + path for path in PATHS})
        identifiers = set()
        for path, methods in self.spec["paths"].items():
            for method, operation in methods.items():
                self.assertIn(method, actual["paths"][path])
                self.assertEqual(
                    operation.get("requestBody"),
                    actual["paths"][path][method].get("requestBody"),
                )
                self.assertNotIn(operation["operationId"], identifiers)
                identifiers.add(operation["operationId"])
        for name, schema in self.spec["components"]["schemas"].items():
            self.assertEqual(schema, actual["components"]["schemas"][name])

    def test_operational_bearer_scope_is_not_misrepresented(self):
        paths = self.spec["paths"]
        self.assertEqual(
            paths["/api/v1/external/reservations"]["post"]["security"],
            [{"PartnerReservationKey": []}],
        )
        self.assertEqual(
            paths["/api/v1/tickets/{ticket_id}/whatsapp"]["post"]["security"],
            [{"RotafySession": [], "RotafyCSRF": []}],
        )
        self.assertEqual(paths["/api/v1/public/mobile-version"]["get"]["security"], [])

    def test_payload_examples_validate_against_live_input_models(self):
        from app.boarding import BoardingCommand, JourneyCommand, TicketMessage
        from app.operations import Trip, Vehicle
        from app.public_sales import KeyCreate, Paid, Tracking
        from app.reservations import Availability, Reservation, ReservationStatus
        from app.schemas import Login, UserCreate
        from app.whatsapp import ManualMessage

        pairs = {
            "login": Login,
            "create_driver": UserCreate,
            "create_vehicle": Vehicle,
            "create_trip": Trip,
            "availability": Availability,
            "create_reservation": Reservation,
            "send_reservation": ManualMessage,
            "send_ticket": TicketMessage,
            "start_journey": JourneyCommand,
            "scan": Tracking,
            "board": BoardingCommand,
            "disembark": BoardingCommand,
            "complete_journey": JourneyCommand,
            "paid": Paid,
            "cancel_reservation": ReservationStatus,
            "integration_key": KeyCreate,
        }
        for key, model in pairs.items():
            with self.subTest(example=key):
                model.model_validate(self.examples[key])

    def test_documented_absolute_routes_exist(self):
        source = (self.directory / "README.md").read_text(encoding="utf-8")
        normalize = lambda path: re.sub(r"\{[^}]+\}", "{}", path)
        implemented = {
            (method.upper(), normalize(path.replace("/api/v1", "", 1)))
            for path, methods in self.spec["paths"].items()
            for method in methods
        }
        for method, path in re.findall(
            r"\b(GET|POST|PUT|PATCH|DELETE|HEAD)\s+(/[A-Za-z0-9_/{\}.-]+)", source
        ):
            self.assertIn(
                (method, normalize(path.replace("/api/v1", "", 1))), implemented
            )

    def test_postman_requests_point_to_documented_routes(self):
        collection = json.loads(
            (self.directory / "rotafy.postman_collection.json").read_text(
                encoding="utf-8"
            )
        )
        normalize = lambda value: re.sub(r"\{[^}]+\}", "{}", value)
        implemented = {
            (method.upper(), normalize(path))
            for path, methods in self.spec["paths"].items()
            for method in methods
        }
        for folder in collection["item"]:
            for item in folder["item"]:
                request = item["request"]
                path = request["url"].replace("{{base_url}}", "/api/v1").split("?")[0]
                path = re.sub(r"\{\{(\w+)\}\}", r"{\1}", path)
                self.assertIn((request["method"], normalize(path)), implemented)
                if "body" in request:
                    raw = re.sub(
                        r"\{\{(\w+)\}\}",
                        lambda m: "0" if m[1] == "presence_version" else "placeholder",
                        request["body"]["raw"],
                    )
                    json.loads(raw)


if __name__ == "__main__":
    unittest.main()
