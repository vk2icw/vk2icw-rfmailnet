#!/usr/bin/env python3
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

VERSION = "0.2"
INBOX_DIR = "/var/rfmailnet/inbox"


class RFMailHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Health/status endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        message = {
            "status": "OK",
            "node": "RFMailNet Gateway",
            "version": VERSION,
            "inbox_path": INBOX_DIR,
        }
        self.wfile.write(json.dumps(message).encode())

    def do_POST(self):
        """Receive and save incoming RFMail messages."""
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0

        body = self.rfile.read(content_length).decode(errors="replace")

        try:
            msg = json.loads(body)
            msgid = str(msg.get("msgid", "unknown")).strip() or "unknown"

            # Ensure inbox exists
            os.makedirs(INBOX_DIR, exist_ok=True)

            # Save the message to disk
            filename = os.path.join(INBOX_DIR, f"{msgid}.json")
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(msg, f, indent=2, ensure_ascii=False)

            print(f"Saved RFMail message {msgid} to {filename}")
            response = {"status": "saved", "msgid": msgid}
        except Exception as e:
            print(f"Error handling POST: {e}")
            response = {"status": "error", "error": str(e)}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    # Keep server logs tidy (optional)
    def log_message(self, format, *args):
        return


if __name__ == "__main__":
        print(f"RFMailNet Gateway v{VERSION} starting…")
        print("Listening on http://0.0.0.0:8080")
        print(f"Inbox directory: {INBOX_DIR}")

        # Ensure inbox exists at startup
        os.makedirs(INBOX_DIR, exist_ok=True)

        server = HTTPServer(("", 8080), RFMailHandler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nGateway stopped.")
        finally:
            server.server_close()
