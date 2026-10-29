import tempfile
import unittest
from pathlib import Path

import app


class HandlerDouble:
    """Exercises HTTP route methods without binding a sandbox-blocked loopback socket."""

    def __init__(self, path, payload=None):
        self.path = path
        self.payload = payload
        self.response = None

    def _write_json(self, status, payload):
        self.response = (int(status), "json", payload)

    def _write_html(self, status, page):
        self.response = (int(status), "html", page)

    def _read_json(self):
        return self.payload

    def _invoice_id_from_path(self, path):
        return app.InvoiceHandler._invoice_id_from_path(self, path)


class InvoiceSystemTests(unittest.TestCase):
    def setUp(self):
        Path("work").mkdir(exist_ok=True)
        self.temp_directory = tempfile.TemporaryDirectory(dir="work")
        self.original_store = app.STORE
        self.original_version = app.APP_VERSION
        self.data_file = Path(self.temp_directory.name) / "invoices.json"
        app.STORE = app.InvoiceStore(self.data_file)

    def tearDown(self):
        app.STORE = self.original_store
        app.APP_VERSION = self.original_version
        self.temp_directory.cleanup()

    @staticmethod
    def invoice_payload(customer="Acme Corp", description="Consulting services", quantity=2, unit_price="125.50"):
        return {
            "customerName": customer,
            "invoiceDate": "2026-10-29",
            "status": "Draft",
            "items": [{"description": description, "quantity": quantity, "unitPrice": unit_price}],
        }

    def test_v1_creates_lists_and_calculates_total(self):
        app.APP_VERSION = "v1"
        invoice = app.STORE.create(app.validate_invoice_payload(self.invoice_payload()))
        self.assertEqual(invoice["id"], "INV-1001")
        self.assertEqual(invoice["total"], "251.00")
        self.assertEqual(len(app.STORE.list()), 1)
        self.assertFalse(app.capability_at_least("v2"))
        self.assertIn("Create invoice", app.render_app())
        self.assertNotIn("Saved invoices", app.render_app())

    def test_v2_edits_an_existing_invoice(self):
        app.APP_VERSION = "v2"
        invoice = app.STORE.create(app.validate_invoice_payload(self.invoice_payload()))
        changed = self.invoice_payload(customer="Globex", quantity=3, unit_price="200")
        changed["status"] = "Sent"
        updated = app.STORE.update(invoice["id"], app.validate_invoice_payload(changed))
        self.assertEqual(updated["customerName"], "Globex")
        self.assertEqual(updated["status"], "Sent")
        self.assertEqual(updated["total"], "600.00")
        self.assertTrue(app.capability_at_least("v2"))
        page = app.render_app()
        self.assertIn("Saved invoices", page)
        self.assertIn("Edit invoice", page)
        self.assertIn("const supportsDetails = false", page)

    def test_v3_renders_dedicated_invoice_details(self):
        app.APP_VERSION = "v3"
        invoice = app.STORE.create(app.validate_invoice_payload(self.invoice_payload()))
        page = app.render_invoice_details(invoice)
        self.assertTrue(app.capability_at_least("v3"))
        self.assertIn("Invoice details", page)
        self.assertIn(invoice["id"], page)
        self.assertIn("Consulting services", page)
        self.assertIn("$251.00", page)
        self.assertIn("View details", app.render_app())

    def test_http_route_methods_create_edit_and_render_details_without_sockets(self):
        app.APP_VERSION = "v1"
        create = HandlerDouble("/api/invoices", self.invoice_payload())
        app.InvoiceHandler.do_POST(create)
        self.assertEqual(create.response[0:2], (201, "json"))
        invoice_id = create.response[2]["invoice"]["id"]

        edit_from_v1 = HandlerDouble(f"/api/invoices/{invoice_id}", self.invoice_payload(customer="Globex"))
        app.InvoiceHandler.do_PUT(edit_from_v1)
        self.assertEqual(edit_from_v1.response[0], 403)

        app.APP_VERSION = "v2"
        edit_from_v2 = HandlerDouble(f"/api/invoices/{invoice_id}", self.invoice_payload(customer="Globex"))
        app.InvoiceHandler.do_PUT(edit_from_v2)
        self.assertEqual(edit_from_v2.response[0:2], (200, "json"))
        self.assertEqual(edit_from_v2.response[2]["invoice"]["customerName"], "Globex")

        app.APP_VERSION = "v3"
        details = HandlerDouble(f"/v3/invoices/{invoice_id}")
        app.InvoiceHandler.do_GET(details)
        self.assertEqual(details.response[0:2], (200, "html"))
        self.assertIn("Invoice details", details.response[2])

    def test_json_storage_reloads_after_restart(self):
        created = app.STORE.create(app.validate_invoice_payload(self.invoice_payload()))
        reloaded = app.InvoiceStore(self.data_file)
        self.assertEqual(reloaded.get(created["id"])["total"], "251.00")

    def test_invalid_invoice_is_rejected(self):
        invalid = self.invoice_payload(quantity=0)
        with self.assertRaisesRegex(app.InvoiceValidationError, "quantity"):
            app.validate_invoice_payload(invalid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
