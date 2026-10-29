"""A small, dependency-free Invoice System for the Agile DevOps assignment.

The APP_VERSION setting deliberately controls the available capability in each
Docker/Kubernetes release:
    v1 - create invoices
    v2 - create and edit invoices
    v3 - create, edit, list, and view dedicated invoice details pages
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


VERSION_LEVELS = {"v1": 1, "v2": 2, "v3": 3}
APP_VERSION = os.environ.get("APP_VERSION", "v1").strip().lower()
if APP_VERSION not in VERSION_LEVELS:
    APP_VERSION = "v1"

APP_PORT = int(os.environ.get("APP_PORT", "8080"))
DATA_FILE = Path(os.environ.get("DATA_FILE", "data/invoices.json"))
MAX_REQUEST_BYTES = 64 * 1024
INVOICE_ID_PATTERN = re.compile(r"^INV-\d{4,}$")


class InvoiceValidationError(ValueError):
    """Raised when an API request does not contain a usable invoice."""


def money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def validate_invoice_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise InvoiceValidationError("The request body must be a JSON object.")

    customer_name = str(payload.get("customerName", "")).strip()
    if not customer_name:
        raise InvoiceValidationError("Customer name is required.")
    if len(customer_name) > 100:
        raise InvoiceValidationError("Customer name must be 100 characters or fewer.")

    invoice_date = str(payload.get("invoiceDate", "")).strip() or date.today().isoformat()
    try:
        date.fromisoformat(invoice_date)
    except ValueError as exc:
        raise InvoiceValidationError("Invoice date must use YYYY-MM-DD format.") from exc

    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise InvoiceValidationError("At least one invoice item is required.")

    items = []
    total = Decimal("0")
    for index, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, dict):
            raise InvoiceValidationError(f"Item {index} must be an object.")
        description = str(raw_item.get("description", "")).strip()
        if not description:
            raise InvoiceValidationError(f"Item {index} description is required.")
        if len(description) > 160:
            raise InvoiceValidationError(f"Item {index} description is too long.")

        try:
            quantity = int(raw_item.get("quantity"))
        except (TypeError, ValueError) as exc:
            raise InvoiceValidationError(f"Item {index} quantity must be a whole number.") from exc
        if quantity < 1 or quantity > 100000:
            raise InvoiceValidationError(f"Item {index} quantity must be between 1 and 100000.")

        try:
            unit_price = Decimal(str(raw_item.get("unitPrice")))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise InvoiceValidationError(f"Item {index} unit price must be a number.") from exc
        if unit_price <= 0 or unit_price > Decimal("100000000"):
            raise InvoiceValidationError(f"Item {index} unit price must be greater than zero.")

        line_total = unit_price * quantity
        total += line_total
        items.append(
            {
                "description": description,
                "quantity": quantity,
                "unitPrice": money(unit_price),
                "lineTotal": money(line_total),
            }
        )

    status = str(payload.get("status", "Draft")).strip().title() or "Draft"
    if status not in {"Draft", "Sent", "Paid"}:
        raise InvoiceValidationError("Status must be Draft, Sent, or Paid.")

    return {
        "customerName": customer_name,
        "invoiceDate": invoice_date,
        "items": items,
        "total": money(total),
        "status": status,
    }


class InvoiceStore:
    """JSON-backed storage so data survives restarts when /data is mounted."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.invoices: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as data_file:
                records = json.load(data_file)
            if isinstance(records, list):
                self.invoices = {
                    record["id"]: record
                    for record in records
                    if isinstance(record, dict) and INVOICE_ID_PATTERN.fullmatch(str(record.get("id", "")))
                }
        except (OSError, json.JSONDecodeError):
            self.invoices = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=self.path.parent, delete=False
        ) as temporary_file:
            json.dump(list(self.invoices.values()), temporary_file, indent=2)
            temporary_file.write("\n")
            temporary_path = Path(temporary_file.name)
        temporary_path.replace(self.path)

    def _next_id(self) -> str:
        numbers = [int(invoice_id.split("-", 1)[1]) for invoice_id in self.invoices]
        return f"INV-{max(numbers, default=1000) + 1:04d}"

    def create(self, invoice: dict) -> dict:
        with self.lock:
            now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            created = {"id": self._next_id(), "createdAt": now, "updatedAt": now, **invoice}
            self.invoices[created["id"]] = created
            self._save()
            return deepcopy(created)

    def list(self) -> list[dict]:
        with self.lock:
            return deepcopy(sorted(self.invoices.values(), key=lambda invoice: invoice["id"], reverse=True))

    def get(self, invoice_id: str) -> dict | None:
        with self.lock:
            invoice = self.invoices.get(invoice_id.upper())
            return deepcopy(invoice) if invoice else None

    def update(self, invoice_id: str, replacement: dict) -> dict | None:
        with self.lock:
            invoice_id = invoice_id.upper()
            existing = self.invoices.get(invoice_id)
            if not existing:
                return None
            updated = {
                "id": invoice_id,
                "createdAt": existing["createdAt"],
                "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                **replacement,
            }
            self.invoices[invoice_id] = updated
            self._save()
            return deepcopy(updated)


STORE = InvoiceStore(DATA_FILE)


def capability_at_least(version: str) -> bool:
    return VERSION_LEVELS[APP_VERSION] >= VERSION_LEVELS[version]


def html_page(title: str, body: str, script: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; color: #243746; background: #f4f7f6; }}
    body {{ margin: 0; background: #f4f7f6; }}
    main {{ max-width: 900px; margin: 0 auto; padding: 32px 20px 48px; }}
    .card {{ background: #fff; padding: 26px 30px; border-radius: 10px; box-shadow: 0 3px 14px rgba(0, 0, 0, .10); margin-top: 20px; }}
    h1 {{ margin: 0 0 8px; font-size: 2rem; }} h2 {{ margin-top: 0; font-size: 1.35rem; }} h3 {{ margin: 0 0 10px; }} p {{ line-height: 1.5; }}
    .badge {{ color: #fff; border-radius: 4px; font-size: .85rem; padding: 5px 9px; vertical-align: middle; }}
    .v1 {{ background: #2ecc71; }} .v2 {{ background: #e67e22; }} .v3 {{ background: #8e44ad; }}
    .notice {{ background: #edf7ff; border-left: 4px solid #3498db; padding: 10px 13px; margin: 15px 0; }} .success {{ background: #e9f8ef; border-left-color: #2ecc71; }} .error {{ background: #fff0f0; border-left-color: #e74c3c; }}
    nav {{ display: flex; gap: 18px; flex-wrap: wrap; }} nav a {{ font-weight: bold; text-decoration: none; }} .v1-link {{ color: #27ae60; }} .v2-link {{ color: #d35400; }} .v3-link {{ color: #8e44ad; }}
    form {{ display: grid; gap: 12px; }} label {{ display: grid; gap: 5px; font-weight: bold; }} input, select {{ box-sizing: border-box; width: 100%; padding: 9px; border: 1px solid #aab7b8; border-radius: 4px; font: inherit; }}
    button {{ width: fit-content; border: 0; border-radius: 4px; background: #3498db; color: #fff; cursor: pointer; font: inherit; font-weight: bold; padding: 10px 16px; }} button:hover {{ filter: brightness(.94); }} button.secondary {{ background: #e67e22; }} button.details {{ background: #8e44ad; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }} .hidden {{ display: none; }} .invoice-list {{ display: grid; gap: 12px; }} .invoice {{ border: 1px solid #dce3e5; border-radius: 7px; padding: 14px; }} .invoice p {{ margin: 5px 0; }} .actions {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }}
    table {{ border-collapse: collapse; width: 100%; }} th, td {{ border-bottom: 1px solid #dce3e5; padding: 9px; text-align: left; }} .total {{ font-size: 1.12rem; font-weight: bold; }}
    @media (max-width: 600px) {{ main {{ padding: 22px 13px; }} .card {{ padding: 20px; }} .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body><main>{body}</main>{script}</body>
</html>"""


def render_app() -> str:
    feature_text = {
        "v1": "Create invoices with a customer, item details, and an automatically calculated total.",
        "v2": "Create invoices, list saved invoices, and edit existing invoice details.",
        "v3": "Create and edit invoices, then open a dedicated page with the full invoice details.",
    }[APP_VERSION]
    label = {"v1": "Create Invoice", "v2": "Edit Invoice", "v3": "View Invoice Details"}[APP_VERSION]
    create_form = """
      <section class="card">
        <h2>Create invoice</h2><p>Enter one invoice item. The server calculates and saves the total.</p>
        <form id="create-form">
          <div class="grid"><label>Customer name <input name="customerName" maxlength="100" required placeholder="Acme Corp"></label><label>Invoice date <input name="invoiceDate" type="date" required></label></div>
          <div class="grid"><label>Item description <input name="description" maxlength="160" required placeholder="Consulting services"></label><label>Quantity <input name="quantity" type="number" min="1" value="1" required></label></div>
          <label>Unit price (USD) <input name="unitPrice" type="number" min="0.01" step="0.01" required placeholder="1200.00"></label>
          <button type="submit">Generate invoice</button>
        </form>
      </section>"""
    management = """
      <section class="card"><h2>Saved invoices</h2><p>Version 2 adds invoice history and editing. Version 3 also offers a dedicated details page.</p><div id="invoice-list" class="invoice-list"><p>Loading saved invoices...</p></div></section>
      <section id="edit-card" class="card hidden"><h2>Edit invoice <span id="editing-id"></span></h2>
        <form id="edit-form"><div class="grid"><label>Customer name <input name="customerName" maxlength="100" required></label><label>Invoice date <input name="invoiceDate" type="date" required></label></div>
        <div class="grid"><label>Item description <input name="description" maxlength="160" required></label><label>Quantity <input name="quantity" type="number" min="1" required></label></div>
        <div class="grid"><label>Unit price (USD) <input name="unitPrice" type="number" min="0.01" step="0.01" required></label><label>Status <select name="status"><option>Draft</option><option>Sent</option><option>Paid</option></select></label></div>
        <div class="actions"><button class="secondary" type="submit">Save changes</button><button type="button" id="cancel-edit">Cancel</button></div></form>
      </section>""" if capability_at_least("v2") else ""
    script = f"""
<script>
const supportsEditing = {str(capability_at_least("v2")).lower()};
const supportsDetails = {str(capability_at_least("v3")).lower()};
let editingInvoiceId = null;
document.querySelector('[name="invoiceDate"]').value = new Date().toISOString().slice(0, 10);
function showMessage(text, kind = 'success') {{ const old = document.getElementById('message'); if (old) old.remove(); const message = document.createElement('p'); message.id = 'message'; message.className = `notice ${{kind}}`; message.textContent = text; document.querySelector('nav').after(message); }}
function formPayload(form) {{ const data = new FormData(form); return {{ customerName: data.get('customerName'), invoiceDate: data.get('invoiceDate'), status: data.get('status') || 'Draft', items: [{{ description: data.get('description'), quantity: Number(data.get('quantity')), unitPrice: data.get('unitPrice') }}] }}; }}
async function request(url, options = {{}}) {{ const response = await fetch(url, options); const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Request failed.'); return body; }}
async function createInvoice(event) {{ event.preventDefault(); try {{ const result = await request('/api/invoices', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(formPayload(event.currentTarget)) }}); event.currentTarget.reset(); document.querySelector('[name="invoiceDate"]').value = new Date().toISOString().slice(0, 10); showMessage(`Invoice ${{result.invoice.id}} saved. Total: $${{result.invoice.total}}.`); if (supportsEditing) refreshInvoices(); }} catch (error) {{ showMessage(error.message, 'error'); }} }}
function invoiceCard(invoice) {{ const card = document.createElement('article'); card.className = 'invoice'; const heading = document.createElement('h3'); heading.textContent = `${{invoice.id}} - ${{invoice.customerName}}`; card.append(heading); const summary = document.createElement('p'); summary.textContent = `${{invoice.invoiceDate}} | ${{invoice.status}} | Total: $${{invoice.total}}`; card.append(summary); const actions = document.createElement('div'); actions.className = 'actions'; const edit = document.createElement('button'); edit.className = 'secondary'; edit.type = 'button'; edit.textContent = 'Edit invoice'; edit.addEventListener('click', () => beginEdit(invoice)); actions.append(edit); if (supportsDetails) {{ const details = document.createElement('button'); details.className = 'details'; details.type = 'button'; details.textContent = 'View details'; details.addEventListener('click', () => location.assign(`/v3/invoices/${{encodeURIComponent(invoice.id)}}`)); actions.append(details); }} card.append(actions); return card; }}
async function refreshInvoices() {{ try {{ const result = await request('/api/invoices'); const list = document.getElementById('invoice-list'); list.replaceChildren(); if (!result.invoices.length) {{ const empty = document.createElement('p'); empty.textContent = 'No invoices saved yet. Create one above.'; list.append(empty); return; }} result.invoices.forEach(invoice => list.append(invoiceCard(invoice))); }} catch (error) {{ showMessage(error.message, 'error'); }} }}
function beginEdit(invoice) {{ editingInvoiceId = invoice.id; const form = document.getElementById('edit-form'); const item = invoice.items[0]; form.customerName.value = invoice.customerName; form.invoiceDate.value = invoice.invoiceDate; form.description.value = item.description; form.quantity.value = item.quantity; form.unitPrice.value = item.unitPrice; form.status.value = invoice.status; document.getElementById('editing-id').textContent = invoice.id; document.getElementById('edit-card').classList.remove('hidden'); document.getElementById('edit-card').scrollIntoView({{behavior: 'smooth'}}); }}
async function saveEdit(event) {{ event.preventDefault(); if (!editingInvoiceId) return; try {{ const result = await request(`/api/invoices/${{encodeURIComponent(editingInvoiceId)}}`, {{ method: 'PUT', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(formPayload(event.currentTarget)) }}); showMessage(`Invoice ${{result.invoice.id}} updated. Total: $${{result.invoice.total}}.`); editingInvoiceId = null; document.getElementById('edit-card').classList.add('hidden'); refreshInvoices(); }} catch (error) {{ showMessage(error.message, 'error'); }} }}
document.getElementById('create-form').addEventListener('submit', createInvoice);
if (supportsEditing) {{ document.getElementById('edit-form').addEventListener('submit', saveEdit); document.getElementById('cancel-edit').addEventListener('click', () => document.getElementById('edit-card').classList.add('hidden')); refreshInvoices(); }}
</script>"""
    body = f"""<nav><a class="{APP_VERSION}-link" href="/">[{APP_VERSION.upper()}: {label}]</a></nav>
      <section class="card"><h1>Invoice System <span class="badge {APP_VERSION}">Version {APP_VERSION[1:]}</span></h1><p>{feature_text}</p><p class="notice">Invoices are stored in <code>{DATA_FILE}</code>. Mount <code>/data</code> in Docker to retain them across container replacement.</p></section>
      {create_form}{management}"""
    return html_page(f"Invoice System - {APP_VERSION.upper()}", body, script)


def render_invoice_details(invoice: dict) -> str:
    rows = "".join(f"<tr><td>{item['description']}</td><td>{item['quantity']}</td><td>${item['unitPrice']}</td><td>${item['lineTotal']}</td></tr>" for item in invoice["items"])
    body = f"""<nav><a class="v3-link" href="/">[V3: Back to invoices]</a></nav>
      <section class="card"><h1>Invoice details <span class="badge v3">Version 3</span></h1><h2>{invoice['id']} - {invoice['customerName']}</h2><p><strong>Invoice date:</strong> {invoice['invoiceDate']} &nbsp; <strong>Status:</strong> {invoice['status']}</p>
      <table><thead><tr><th>Item</th><th>Qty</th><th>Unit price</th><th>Line total</th></tr></thead><tbody>{rows}</tbody></table><p class="total">Invoice total: ${invoice['total']}</p><p>Created: {invoice['createdAt']}<br>Last updated: {invoice['updatedAt']}</p></section>"""
    return html_page(f"Invoice {invoice['id']} details", body)


class InvoiceHandler(BaseHTTPRequestHandler):
    server_version = "InvoiceSystem/1.0"

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _write_json(self, status: HTTPStatus, payload: dict) -> None:
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _write_html(self, status: HTTPStatus, page: str) -> None:
        content = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json(self) -> dict:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise InvoiceValidationError("Content-Length must be valid.") from exc
        if content_length < 1 or content_length > MAX_REQUEST_BYTES:
            raise InvoiceValidationError("Request body must be between 1 and 65536 bytes.")
        try:
            return json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvoiceValidationError("Request body must be valid JSON.") from exc

    def _invoice_id_from_path(self, path: str) -> str | None:
        prefix = "/api/invoices/"
        if not path.startswith(prefix):
            return None
        invoice_id = unquote(path[len(prefix):]).upper()
        return invoice_id if INVOICE_ID_PATTERN.fullmatch(invoice_id) else None

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._write_json(HTTPStatus.OK, {"status": "ok", "version": APP_VERSION})
        elif path == "/api/invoices":
            self._write_json(HTTPStatus.OK, {"invoices": STORE.list()})
        elif invoice_id := self._invoice_id_from_path(path):
            invoice = STORE.get(invoice_id)
            if not invoice:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "Invoice not found."})
            elif not capability_at_least("v3"):
                self._write_json(HTTPStatus.FORBIDDEN, {"error": "Invoice details require Version 3."})
            else:
                self._write_json(HTTPStatus.OK, {"invoice": invoice})
        elif path.startswith("/v3/invoices/"):
            invoice_id = unquote(path[len("/v3/invoices/"):]).upper()
            invoice = STORE.get(invoice_id)
            if not capability_at_least("v3"):
                self._write_html(HTTPStatus.NOT_FOUND, html_page("Not found", "<h1>Not found</h1>"))
            elif not invoice:
                self._write_html(HTTPStatus.NOT_FOUND, html_page("Invoice not found", "<h1>Invoice not found</h1>"))
            else:
                self._write_html(HTTPStatus.OK, render_invoice_details(invoice))
        elif path in ("/", "", f"/{APP_VERSION}"):
            self._write_html(HTTPStatus.OK, render_app())
        else:
            self._write_html(HTTPStatus.NOT_FOUND, html_page("Not found", "<h1>Not found</h1>"))

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/invoices":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Route not found."})
            return
        try:
            invoice = STORE.create(validate_invoice_payload(self._read_json()))
        except InvoiceValidationError as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._write_json(HTTPStatus.CREATED, {"invoice": invoice})

    def do_PUT(self) -> None:
        invoice_id = self._invoice_id_from_path(urlparse(self.path).path)
        if not invoice_id:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Route not found."})
            return
        if not capability_at_least("v2"):
            self._write_json(HTTPStatus.FORBIDDEN, {"error": "Editing invoices requires Version 2."})
            return
        try:
            invoice = STORE.update(invoice_id, validate_invoice_payload(self._read_json()))
        except InvoiceValidationError as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if not invoice:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Invoice not found."})
            return
        self._write_json(HTTPStatus.OK, {"invoice": invoice})

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, POST, PUT, OPTIONS")
        self.end_headers()


if __name__ == "__main__":
    print(f"Invoice System {APP_VERSION.upper()} listening on port {APP_PORT}")
    ThreadingHTTPServer(("0.0.0.0", APP_PORT), InvoiceHandler).serve_forever()
