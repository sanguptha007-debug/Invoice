from http.server import SimpleHTTPRequestHandler, HTTPServer

class InvoiceHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
        # HTML Content specific to Version 1
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Invoice System - v1</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background-color: #f4f7f6; }
                .card { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 500px; }
                h1 { color: #2c3e50; }
                .badge { background-color: #2ecc71; color: white; padding: 5px 10px; border-radius: 4px; font-size: 14px; }
                button { background-color: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin-top: 15px; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Invoice System <span class="badge">Version 1</span></h1>
                <h3>Create &ndash; Generate invoice</h3>
                <p>Enter details below to generate a new invoice stub.</p>
                <input type="text" placeholder="Client Name" style="width:90%; padding:8px; margin-bottom:10px;"><br>
                <input type="number" placeholder="Amount ($)" style="width:90%; padding:8px; margin-bottom:10px;"><br>
                <button onclick="alert('Invoice Generated Successfully!')">Generate Invoice</button>
            </div>
        </body>
        </html>
        """
        self.wfile.write(bytes(html, "utf8"))

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 80), InvoiceHandler)
    print("Server running on port 80...")
    server.serve_forever()
