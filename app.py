import os
import urllib.parse
from http.server import SimpleHTTPRequestHandler, HTTPServer

# Support version selection via environment variable or URL routing
DEFAULT_VERSION = os.environ.get("APP_VERSION", "v1").lower()

def render_page(active_version):
    nav_html = """
        <div style="margin-bottom: 20px;">
            <a href="/v1" style="margin-right: 15px; text-decoration: none; font-weight: bold; color: #2ecc71;">[v1: Create Invoice]</a>
            <a href="/v2" style="margin-right: 15px; text-decoration: none; font-weight: bold; color: #e67e22;">[v2: Edit Invoice]</a>
            <a href="/v3" style="text-decoration: none; font-weight: bold; color: #9b59b6;">[v3: View Invoice]</a>
        </div>
    """

    if active_version == "v2":
        card_content = """
            <div class="card">
                <h1>Invoice System <span class="badge" style="background-color: #e67e22;">Version 2</span></h1>
                <h3>Edit &ndash; Modify invoice</h3>
                <p>Enter Invoice ID below to modify an existing invoice record.</p>
                <input type="text" placeholder="Invoice ID (e.g. INV-1001)" style="width:90%; padding:8px; margin-bottom:10px;"><br>
                <input type="text" placeholder="Client Name" style="width:90%; padding:8px; margin-bottom:10px;"><br>
                <input type="number" placeholder="Amount ($)" style="width:90%; padding:8px; margin-bottom:10px;"><br>
                <select style="width:95%; padding:8px; margin-bottom:10px;">
                    <option value="draft">Status: Draft</option>
                    <option value="sent">Status: Sent</option>
                    <option value="paid">Status: Paid</option>
                </select><br>
                <button style="background-color: #e67e22;" onclick="alert('Invoice Updated Successfully!')">Update Invoice</button>
            </div>
        """
        title = "Invoice System - v2"
    elif active_version == "v3":
        card_content = """
            <div class="card">
                <h1>Invoice System <span class="badge" style="background-color: #9b59b6;">Version 3</span></h1>
                <h3>View &ndash; Invoice details &amp; Preview</h3>
                <p>Search and inspect generated invoices with full itemized breakdown.</p>
                <input type="text" placeholder="Search by Invoice ID or Client" style="width:90%; padding:8px; margin-bottom:10px;"><br>
                <div style="background:#f8f9fa; border:1px solid #ddd; padding:15px; border-radius:6px; margin: 10px 0; text-align: left;">
                    <strong>Invoice #INV-1001</strong> &mdash; Acme Corp<br>
                    <span style="color:#7f8c8d; font-size:13px;">Date: 2026-10-28 | Status: Paid</span>
                    <hr style="border:none; border-top:1px solid #eee; margin:10px 0;">
                    <div>Item 1: Consulting Services - $1,200.00</div>
                    <div>Item 2: Cloud Infrastructure - $800.00</div>
                    <div style="font-weight:bold; margin-top:8px;">Total: $2,000.00</div>
                </div>
                <button style="background-color: #9b59b6;" onclick="alert('Invoice Loaded Successfully!')">View Invoice</button>
            </div>
        """
        title = "Invoice System - v3"
    else:
        # Default Version 1 (Preserves exact original structure and content)
        card_content = """
            <div class="card">
                <h1>Invoice System <span class="badge">Version 1</span></h1>
                <h3>Create &ndash; Generate invoice</h3>
                <p>Enter details below to generate a new invoice stub.</p>
                <input type="text" placeholder="Client Name" style="width:90%; padding:8px; margin-bottom:10px;"><br>
                <input type="number" placeholder="Amount ($)" style="width:90%; padding:8px; margin-bottom:10px;"><br>
                <button onclick="alert('Invoice Generated Successfully!')">Generate Invoice</button>
            </div>
        """
        title = "Invoice System - v1"

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f4f7f6; }}
        .card {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 500px; }}
        h1 {{ color: #2c3e50; }}
        .badge {{ background-color: #2ecc71; color: white; padding: 5px 10px; border-radius: 4px; font-size: 14px; }}
        button {{ background-color: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin-top: 15px; }}
    </style>
</head>
<body>
    {nav_html}
    {card_content}
</body>
</html>
"""

class InvoiceHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.strip("/").lower()

        if path in ("v2", "edit"):
            version = "v2"
        elif path in ("v3", "view"):
            version = "v3"
        elif path in ("v1", "create"):
            version = "v1"
        else:
            version = DEFAULT_VERSION

        html = render_page(version)
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(bytes(html, "utf8"))

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 80), InvoiceHandler)
    print("Server running on port 80...")
    server.serve_forever()
