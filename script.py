import hashlib
import json
import os
import webbrowser 
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode 

import requests

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email"
]
HOST = "localhost"
PORT = 0

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.server = self.server
        self.server: "Server"
        self.server.query_params = dict(parse_qsl(self.path.split("?")[1]))
        self.wfile.write(b"<h1>Authorised!</h1>")
        
class Server(HTTPServer):
    def __init__(self, host: str, port: int):
        super().__init__((host, port), RequestHandler)
        self.query_params: dict[str, str] = {}

def authorise(secret: dict[str, str]) -> dict[str, str] :
    server = Server(HOST, PORT)
    actual_port = server.server_address[1]
    redirect_uri = f"{secret['redirect_uris'][0]}:{actual_port}"

    params = {
        "response_type": "code",
        "client_id": secret["client_id"],
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "state": hashlib.sha256(os.urandom(1024)).hexdigest(),
        "access_type": "offline",

    }
    url = f"{secret['auth_uri']}?{urlencode(params)}"
    if not webbrowser.open(url):
        raise RuntimeError("Failed to open web browser for authentication")
    try:
        server.handle_request()
    finally:
        server.server_close()

    if params["state"] != server.query_params.get("state"):
        raise RuntimeError("Invalid state")

    code = server.query_params.get("code")
    if not code:
        raise RuntimeError("Failed to retrieve authorization code")

    params = {
        "grant_type": "authorization_code",
        "client_id": secret["client_id"],
        "client_secret": secret["client_secret"],
        "redirect_uri": redirect_uri,
        "code": code,
    }
    response = requests.post(
        secret["token_uri"],
        data=params,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if response.status_code != 200:
        raise RuntimeError(f"Failed to authorise")
    
    return response.json()
    

def check_access_token(access_token: str) -> dict[str, str]:
    response = requests.post(
        f"https://www.googleapis.com/oauth2/v3/tokeninfo?access_token={access_token}",
    )
    if response.status_code != 200:
        raise RuntimeError("Failed to check access token")
    
    return response.json()

if __name__ == "__main__":
    secret = json.loads(Path("secret.json").read_text())["installed"]
    
    tokens = authorise(secret)
    print(f"Tokens: {tokens}")

    token_info = check_access_token(tokens["access_token"])
    print(f"Token info: {token_info}")