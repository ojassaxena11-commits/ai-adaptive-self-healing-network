import os
import json
import requests
from typing import Dict, Any, List, Optional
import urllib3

from src.utils.logger import logger

# Suppress insecure HTTPS warning if user disables SSL verification for local CML instances
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CMLClient:
    """
    Cisco Modeling Labs (CML) REST API Client.
    Connects to the CML 2.x controller to authenticate, discover lab topologies,
    monitor node execution states, and query or condition virtual links.
    Reads credentials and host configurations securely from environment variables.
    """

    STATUS_NOT_CONFIGURED = "NOT CONFIGURED"
    STATUS_CONNECTING = "CONNECTING"
    STATUS_CONNECTED = "CONNECTED"
    STATUS_ERROR = "ERROR"

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        host: str = "",
        username: str = "",
        password: str = "",
        lab_id: str = "",
        port: Optional[int] = None,
        verify_ssl: Optional[bool] = None
    ):
        self.config = config or {}

        # Load connection parameters from parameters, environment, or config (no hard-coding)
        self.host = host or os.getenv("CML_HOST") or self.config.get("cml", {}).get("host", "")
        self.port = port if port is not None else int(os.getenv("CML_PORT") or self.config.get("cml", {}).get("port", 443))
        self.username = username or os.getenv("CML_USER") or self.config.get("cml", {}).get("username", "")
        self.password = password or os.getenv("CML_PASS") or self.config.get("cml", {}).get("password", "")
        self.lab_id = lab_id or os.getenv("CML_LAB_ID") or self.config.get("cml", {}).get("lab_id", "")

        raw_ssl = verify_ssl if verify_ssl is not None else (os.getenv("CML_VERIFY_SSL") or str(self.config.get("cml", {}).get("verify_ssl", "false")))
        self.verify_ssl = str(raw_ssl).strip().lower() in ("true", "1", "yes") if not isinstance(raw_ssl, bool) else raw_ssl

        self.auth_token: Optional[str] = None
        self.status = self.STATUS_NOT_CONFIGURED if not self.host else self.STATUS_CONNECTING
        self.last_error: Optional[str] = None

    @property
    def token(self) -> Optional[str]:
        return self.auth_token

    @token.setter
    def token(self, val: Optional[str]) -> None:
        self.auth_token = val

    def is_authenticated(self) -> bool:
        """Returns True if a valid authentication token has been obtained."""
        return bool(self.auth_token)

    @property
    def base_url(self) -> str:
        protocol = "https" if self.port in (443, 8443) else "http"
        return f"{protocol}://{self.host}:{self.port}/api/v0"

    def is_configured(self) -> bool:
        """Returns True if minimum required connection parameters are present."""
        return bool(self.host and self.username and self.password)

    def authenticate(self, timeout: float = 4.0) -> bool:
        """
        Authenticates against CML REST API /api/v0/authenticate.
        Obtains JWT bearer token for subsequent REST endpoints.
        """
        if not self.is_configured():
            self.status = self.STATUS_NOT_CONFIGURED
            self.last_error = "CML credentials or host not fully configured in .env"
            return False

        self.status = self.STATUS_CONNECTING
        auth_url = f"{self.base_url}/authenticate"
        payload = {"username": self.username, "password": self.password}

        try:
            logger.info(f"Connecting to CML REST controller at {self.host}:{self.port}...")
            resp = requests.post(
                auth_url,
                json=payload,
                verify=self.verify_ssl,
                timeout=timeout
            )

            if resp.status_code == 200:
                # CML returns JSON token string or object with token
                try:
                    data = resp.json()
                    self.auth_token = data if isinstance(data, str) else data.get("token", "")
                except Exception:
                    self.auth_token = resp.text.strip('"')

                self.status = self.STATUS_CONNECTED
                self.last_error = None
                logger.info(f"Successfully authenticated to CML controller at {self.host}")
                return True
            else:
                self.status = self.STATUS_ERROR
                self.last_error = f"Authentication rejected by CML: HTTP {resp.status_code} ({resp.text[:120]})"
                logger.warning(self.last_error)
                return False

        except requests.exceptions.SSLError as ssl_err:
            self.status = self.STATUS_ERROR
            self.last_error = f"TLS/SSL certificate error connecting to CML at {self.host}: {ssl_err}. Set CML_VERIFY_SSL=false for self-signed certificates."
            logger.error(self.last_error)
            return False
        except requests.exceptions.ConnectionError as conn_err:
            self.status = self.STATUS_ERROR
            self.last_error = f"Could not reach CML controller at {self.host}:{self.port} (Connection Refused or Host Unreachable)."
            logger.warning(self.last_error)
            return False
        except requests.exceptions.Timeout:
            self.status = self.STATUS_ERROR
            self.last_error = f"Connection to CML at {self.host}:{self.port} timed out after {timeout}s."
            logger.warning(self.last_error)
            return False
        except Exception as e:
            self.status = self.STATUS_ERROR
            self.last_error = f"Unexpected CML connection error: {e}"
            logger.error(self.last_error)
            return False

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def get_labs(self, timeout: float = 3.0) -> List[Dict[str, Any]]:
        """Retrieves list of active labs from CML controller."""
        if not self.auth_token and not self.authenticate():
            return []

        try:
            resp = requests.get(
                f"{self.base_url}/labs",
                headers=self._headers(),
                verify=self.verify_ssl,
                timeout=timeout
            )
            if resp.status_code == 200:
                return resp.json() if isinstance(resp.json(), list) else []
            return []
        except Exception as e:
            logger.debug(f"Failed retrieving CML labs: {e}")
            return []

    def get_lab_details(self, lab_id: Optional[str] = None, timeout: float = 3.0) -> Dict[str, Any]:
        """Retrieves details of specified lab."""
        target_lab = lab_id or self.lab_id
        if not target_lab:
            return {}

        if not self.auth_token and not self.authenticate():
            return {}

        try:
            resp = requests.get(
                f"{self.base_url}/labs/{target_lab}",
                headers=self._headers(),
                verify=self.verify_ssl,
                timeout=timeout
            )
            if resp.status_code == 200:
                return resp.json()
            return {}
        except Exception as e:
            logger.debug(f"Failed retrieving CML lab details for {target_lab}: {e}")
            return {}

    def get_nodes(self, lab_id: Optional[str] = None, timeout: float = 3.0) -> List[Dict[str, Any]]:
        """Retrieves nodes within target lab and their current state (BOOTED, STOPPED)."""
        target_lab = lab_id or self.lab_id
        if not target_lab or (not self.auth_token and not self.authenticate()):
            return []

        try:
            resp = requests.get(
                f"{self.base_url}/labs/{target_lab}/nodes",
                headers=self._headers(),
                verify=self.verify_ssl,
                timeout=timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return list(data.values())
            return []
        except Exception as e:
            logger.debug(f"Failed querying CML nodes for lab {target_lab}: {e}")
            return []

    def test_connectivity(self) -> Dict[str, Any]:
        """
        Executes an end-to-end diagnostic connectivity check to CML.
        Returns a structured dictionary with status, reachability, and diagnostics.
        """
        if not self.is_configured():
            return {
                "status": self.STATUS_NOT_CONFIGURED,
                "host": self.host or "Not Set",
                "port": self.port,
                "lab_id": self.lab_id or "Not Set",
                "ssl_verify": self.verify_ssl,
                "authenticated": False,
                "error": "CML configuration is missing in .env. Please set CML_HOST, CML_USER, CML_PASS.",
                "message": "CML NOT CONFIGURED: Parameters missing from environment."
            }

        success = self.authenticate(timeout=3.5)
        if not success:
            return {
                "status": self.STATUS_ERROR,
                "host": self.host,
                "port": self.port,
                "lab_id": self.lab_id,
                "ssl_verify": self.verify_ssl,
                "authenticated": False,
                "error": self.last_error,
                "message": f"CML CONNECTION FAILED: {self.last_error}"
            }

        # Query lab information
        lab_info = self.get_lab_details()
        nodes = self.get_nodes()
        node_summary = [
            {"label": n.get("label", n.get("id", str(n))), "state": n.get("state", "UNKNOWN")}
            if isinstance(n, dict) else {"label": str(n), "state": "UNKNOWN"}
            for n in nodes
        ]

        return {
            "status": self.STATUS_CONNECTED,
            "host": self.host,
            "port": self.port,
            "lab_id": self.lab_id,
            "lab_title": lab_info.get("lab_title", self.lab_id),
            "lab_state": lab_info.get("state", "STARTED"),
            "ssl_verify": self.verify_ssl,
            "authenticated": True,
            "nodes": node_summary,
            "node_count": len(node_summary),
            "error": None,
            "message": f"CML CONNECTED: Authenticated to {self.host}:{self.port} (Lab: {self.lab_id}, Nodes: {len(node_summary)})."
        }
