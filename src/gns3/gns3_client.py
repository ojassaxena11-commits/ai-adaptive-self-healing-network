import os
import json
import configparser
from typing import Dict, Any, List, Optional
import requests
import urllib3

from src.utils.logger import logger

# Suppress insecure HTTPS warning if user disables SSL verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class GNS3Client:
    """
    Official GNS3 Controller REST API Client.
    Connects to the GNS3 server (default: http://localhost:3080) to discover,
    create, and manage network projects, nodes, links, and simulated network states.
    Reads configuration from environment variables, config dictionaries, or local
    GNS3 server settings.
    """

    STATUS_NOT_CONFIGURED = "NOT CONFIGURED"
    STATUS_CONNECTING = "CONNECTING"
    STATUS_CONNECTED = "CONNECTED"
    STATUS_SERVER_OFFLINE = "SERVER OFFLINE"
    STATUS_AUTH_FAILED = "AUTH FAILED"
    STATUS_ERROR = "ERROR"

    PLACEHOLDER_VALUES = {
        "change_me", "your_gns3_host", "your_username", "your_password",
        "todo", "placeholder", "none", "null", "undefined", ""
    }

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
        protocol: Optional[str] = None,
        timeout: float = 4.0
    ):
        self.config = config or {}
        gns3_cfg = self.config.get("gns3", {})

        # Host
        if host is not None:
            raw_host = host
        else:
            raw_host = os.getenv("GNS3_HOST") or gns3_cfg.get("host") or "localhost"

        # Sanitize host
        raw_host = str(raw_host).strip()
        inferred_protocol = "http"
        if raw_host.startswith("https://"):
            inferred_protocol = "https"
            raw_host = raw_host[len("https://"):]
        elif raw_host.startswith("http://"):
            inferred_protocol = "http"
            raw_host = raw_host[len("http://"):]

        if "/" in raw_host:
            raw_host = raw_host.split("/")[0]

        extracted_port = None
        if ":" in raw_host:
            parts = raw_host.split(":")
            raw_host = parts[0]
            try:
                extracted_port = int(parts[1])
            except (ValueError, TypeError):
                pass

        self.host = raw_host or "localhost"
        self.protocol = protocol or os.getenv("GNS3_PROTOCOL") or gns3_cfg.get("protocol") or inferred_protocol

        # Port
        if port is not None:
            self.port = port
        elif extracted_port is not None:
            self.port = extracted_port
        else:
            raw_port = os.getenv("GNS3_PORT") or gns3_cfg.get("port") or 3080
            try:
                self.port = int(raw_port)
            except (ValueError, TypeError):
                self.port = 3080

        # Username and password: env / config / auto-detect from local GNS3 server.ini
        auto_user, auto_pass = self._detect_local_gns3_credentials()

        if username is not None:
            self.username = username.strip()
        else:
            self.username = (os.getenv("GNS3_USER") or gns3_cfg.get("username") or auto_user or "").strip()

        if password is not None:
            self.password = password
        else:
            self.password = os.getenv("GNS3_PASS") or gns3_cfg.get("password") or auto_pass or ""

        # Project ID & Name
        self.project_id = project_id or os.getenv("GNS3_PROJECT_ID") or gns3_cfg.get("project_id", "")
        self.project_name = project_name or os.getenv("GNS3_PROJECT_NAME") or gns3_cfg.get("project_name", "AI-Self-Healing-Network")

        self.timeout = float(timeout)
        self.status = self.STATUS_CONNECTING if self.is_configured() else self.STATUS_NOT_CONFIGURED
        self.last_error: Optional[str] = None
        self.server_version: Optional[str] = None

    @staticmethod
    def _detect_local_gns3_credentials() -> tuple[Optional[str], Optional[str]]:
        """
        Attempts to safely auto-detect credentials from local Windows GNS3 server config
        if the user runs GNS3 locally without explicitly editing .env.
        """
        try:
            appdata = os.getenv("APPDATA", "")
            if not appdata:
                return None, None
            ini_path = os.path.join(appdata, "GNS3", "2.2", "gns3_server.ini")
            if os.path.isfile(ini_path):
                cfg = configparser.ConfigParser()
                cfg.read(ini_path)
                if cfg.has_section("Server"):
                    user = cfg.get("Server", "user", fallback="")
                    pw = cfg.get("Server", "password", fallback="")
                    return user or None, pw or None
        except Exception:
            pass
        return None, None

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}/v2"

    @property
    def auth(self) -> Optional[tuple[str, str]]:
        if self.username and self.password:
            return (self.username, self.password)
        return None

    def is_configured(self) -> bool:
        """Returns True if minimum connection settings are present."""
        if not self.host:
            return False
        if self.host.lower() in self.PLACEHOLDER_VALUES:
            return False
        return True

    def test_connectivity(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Tests connection to GNS3 Controller API v2.
        Returns a structured dictionary with reachability, version, and simple human-readable messages.
        """
        effective_timeout = timeout or self.timeout

        if not self.is_configured():
            self.status = self.STATUS_NOT_CONFIGURED
            self.last_error = "GNS3 host address is not configured."
            return {
                "status": self.STATUS_NOT_CONFIGURED,
                "host": self.host,
                "port": self.port,
                "base_url": self.base_url,
                "authenticated": False,
                "connected": False,
                "version": None,
                "error": self.last_error,
                "message": "Cannot Connect to GNS3: Host address is missing.",
                "diagnostics": [
                    "Verify GNS3_HOST and GNS3_PORT in your .env or settings.",
                    "Default local server is http://localhost:3080"
                ]
            }

        url = f"{self.base_url}/version"
        try:
            logger.info(f"Connecting to GNS3 Controller at {self.base_url}...")
            resp = requests.get(url, auth=self.auth, timeout=effective_timeout)

            if resp.status_code == 200:
                data = resp.json()
                self.server_version = data.get("version", "unknown")
                self.status = self.STATUS_CONNECTED
                self.last_error = None
                logger.info(f"Connected to GNS3 Controller v{self.server_version} at {self.host}:{self.port}")
                return {
                    "status": self.STATUS_CONNECTED,
                    "host": self.host,
                    "port": self.port,
                    "base_url": self.base_url,
                    "authenticated": bool(self.auth),
                    "connected": True,
                    "version": self.server_version,
                    "error": None,
                    "message": f"Connected to GNS3 successfully (v{self.server_version} at {self.host}:{self.port}).",
                    "diagnostics": ["GNS3 Controller API is reachable and responding."]
                }
            elif resp.status_code == 401:
                self.status = self.STATUS_AUTH_FAILED
                self.last_error = "GNS3 server requires authentication (HTTP 401 Unauthorized)."
                logger.warning(self.last_error)
                return {
                    "status": self.STATUS_AUTH_FAILED,
                    "host": self.host,
                    "port": self.port,
                    "base_url": self.base_url,
                    "authenticated": False,
                    "connected": False,
                    "version": None,
                    "error": self.last_error,
                    "message": "Cannot Connect to GNS3: Incorrect username or password.",
                    "diagnostics": [
                        "Check GNS3_USER and GNS3_PASS in your .env file.",
                        "If you use GNS3 local server, check %APPDATA%\\GNS3\\2.2\\gns3_server.ini"
                    ]
                }
            else:
                self.status = self.STATUS_ERROR
                self.last_error = f"GNS3 server returned HTTP {resp.status_code}: {resp.text[:120]}"
                return {
                    "status": self.STATUS_ERROR,
                    "host": self.host,
                    "port": self.port,
                    "base_url": self.base_url,
                    "authenticated": False,
                    "connected": False,
                    "version": None,
                    "error": self.last_error,
                    "message": f"Cannot Connect to GNS3: HTTP error {resp.status_code}",
                    "diagnostics": [f"Server responded with: {resp.text[:150]}"]
                }

        except (requests.exceptions.ConnectionError, requests.exceptions.ConnectTimeout):
            self.status = self.STATUS_SERVER_OFFLINE
            self.last_error = f"Could not reach GNS3 server at {self.host}:{self.port} (Connection Refused)."
            logger.warning(self.last_error)
            return {
                "status": self.STATUS_SERVER_OFFLINE,
                "host": self.host,
                "port": self.port,
                "base_url": self.base_url,
                "authenticated": False,
                "connected": False,
                "version": None,
                "error": self.last_error,
                "message": "Cannot Connect to GNS3: Server is offline or not running.",
                "diagnostics": [
                    f"Ensure GNS3 is opened on your computer.",
                    f"Check that GNS3 server is listening on port {self.port}.",
                    "The dashboard will continue operating safely in Simulation Mode."
                ]
            }
        except requests.exceptions.Timeout:
            self.status = self.STATUS_ERROR
            self.last_error = f"Connection to GNS3 timed out after {effective_timeout}s."
            return {
                "status": self.STATUS_ERROR,
                "host": self.host,
                "port": self.port,
                "base_url": self.base_url,
                "authenticated": False,
                "connected": False,
                "version": None,
                "error": self.last_error,
                "message": "Cannot Connect to GNS3: Connection timed out.",
                "diagnostics": ["GNS3 server took too long to reply. Check your system load or network connection."]
            }
        except Exception as e:
            self.status = self.STATUS_ERROR
            self.last_error = f"Unexpected GNS3 connection error: {e}"
            return {
                "status": self.STATUS_ERROR,
                "host": self.host,
                "port": self.port,
                "base_url": self.base_url,
                "authenticated": False,
                "connected": False,
                "version": None,
                "error": self.last_error,
                "message": f"Cannot Connect to GNS3: {e}",
                "diagnostics": ["Verify your local GNS3 configuration and try again."]
            }

    def get_projects(self, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """Retrieves list of projects from GNS3 server."""
        try:
            resp = requests.get(f"{self.base_url}/projects", auth=self.auth, timeout=timeout or self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            return []
        except Exception as e:
            logger.debug(f"Failed to query GNS3 projects: {e}")
            return []

    def find_project_by_name(self, name: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Finds a project matching name or active open project with similar name."""
        projects = self.get_projects(timeout=timeout)
        # 1. Exact match and opened
        for p in projects:
            if p.get("name") == name and p.get("status") == "opened":
                return p
        # 2. Similar name and opened (e.g. name-1)
        for p in projects:
            if p.get("status") == "opened" and (name in p.get("name", "") or p.get("name", "") in name):
                return p
        # 3. Exact match (any status)
        for p in projects:
            if p.get("name") == name:
                return p
        # 4. Similar match (any status)
        for p in projects:
            if name in p.get("name", "") or p.get("name", "") in name:
                return p
        return None

    def _resolve_project_id(self, project_id: Optional[str] = None) -> Optional[str]:
        """Resolves project ID from argument, instance attribute, or active project matching name."""
        if project_id:
            return project_id
        if self.project_id:
            return self.project_id
        if self.project_name:
            matched = self.find_project_by_name(self.project_name)
            if matched:
                self.project_id = matched.get("project_id")
                return self.project_id
        return None

    def get_project(self, project_id: Optional[str] = None, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Retrieves details of specified project."""
        pid = self._resolve_project_id(project_id)
        if not pid:
            return None
        try:
            resp = requests.get(f"{self.base_url}/projects/{pid}", auth=self.auth, timeout=timeout or self.timeout)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.debug(f"Failed to get GNS3 project {pid}: {e}")
            return None

    def open_project(self, project_id: Optional[str] = None, timeout: Optional[float] = None) -> bool:
        """Opens project if it is currently closed."""
        pid = self._resolve_project_id(project_id)
        if not pid:
            return False
        try:
            resp = requests.post(f"{self.base_url}/projects/{pid}/open", auth=self.auth, timeout=timeout or self.timeout)
            return resp.status_code in (200, 201)
        except Exception as e:
            logger.debug(f"Failed to open GNS3 project {pid}: {e}")
            return False

    def close_project(self, project_id: Optional[str] = None, timeout: Optional[float] = None) -> bool:
        """Closes project."""
        pid = self._resolve_project_id(project_id)
        if not pid:
            return False
        try:
            resp = requests.post(f"{self.base_url}/projects/{pid}/close", auth=self.auth, timeout=timeout or self.timeout)
            return resp.status_code in (200, 201, 204)
        except Exception as e:
            logger.debug(f"Failed to close GNS3 project {pid}: {e}")
            return False

    def create_project(self, name: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Creates a new project in GNS3."""
        try:
            resp = requests.post(
                f"{self.base_url}/projects",
                json={"name": name},
                auth=self.auth,
                timeout=timeout or self.timeout
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                self.project_id = data.get("project_id", self.project_id)
                self.project_name = name
                return data
            return None
        except Exception as e:
            logger.error(f"Failed to create GNS3 project '{name}': {e}")
            return None

    def get_nodes(self, project_id: Optional[str] = None, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """Retrieves nodes in project and their status (started, stopped, suspended)."""
        pid = self._resolve_project_id(project_id)
        if not pid:
            return []
        try:
            resp = requests.get(f"{self.base_url}/projects/{pid}/nodes", auth=self.auth, timeout=timeout or self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            return []
        except Exception as e:
            logger.debug(f"Failed to get nodes for project {pid}: {e}")
            return []

    def get_links(self, project_id: Optional[str] = None, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """Retrieves links in project and their suspension state."""
        pid = self._resolve_project_id(project_id)
        if not pid:
            return []
        try:
            resp = requests.get(f"{self.base_url}/projects/{pid}/links", auth=self.auth, timeout=timeout or self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            return []
        except Exception as e:
            logger.debug(f"Failed to get links for project {pid}: {e}")
            return []

    def get_templates(self, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """Retrieves available appliance and device templates in GNS3."""
        try:
            resp = requests.get(f"{self.base_url}/templates", auth=self.auth, timeout=timeout or self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            return []
        except Exception as e:
            logger.debug(f"Failed to get templates: {e}")
            return []

    def create_node(
        self,
        name: str,
        node_type: str = "ethernet_switch",
        x: int = 0,
        y: int = 0,
        project_id: Optional[str] = None,
        compute_id: str = "local",
        properties: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Creates a node inside the target GNS3 project."""
        pid = project_id or self.project_id
        if not pid:
            return None
        payload: Dict[str, Any] = {
            "name": name,
            "node_type": node_type,
            "compute_id": compute_id,
            "x": x,
            "y": y
        }
        if properties:
            payload["properties"] = properties

        try:
            resp = requests.post(
                f"{self.base_url}/projects/{pid}/nodes",
                json=payload,
                auth=self.auth,
                timeout=timeout or self.timeout
            )
            if resp.status_code in (200, 201):
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Failed to create node '{name}' in project {pid}: {e}")
            return None

    def create_link(
        self,
        node1_id: str,
        port1: int,
        node2_id: str,
        port2: int,
        project_id: Optional[str] = None,
        adapter1: int = 0,
        adapter2: int = 0,
        timeout: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Creates a link between two nodes in the target project."""
        pid = project_id or self.project_id
        if not pid:
            return None
        payload = {
            "nodes": [
                {"node_id": node1_id, "adapter_number": adapter1, "port_number": port1},
                {"node_id": node2_id, "adapter_number": adapter2, "port_number": port2}
            ]
        }
        try:
            resp = requests.post(
                f"{self.base_url}/projects/{pid}/links",
                json=payload,
                auth=self.auth,
                timeout=timeout or self.timeout
            )
            if resp.status_code in (200, 201):
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Failed to create link between {node1_id} and {node2_id}: {e}")
            return None

    def suspend_link(
        self,
        link_id: str,
        suspend: bool = True,
        project_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> bool:
        """
        Suspends or unsuspends a virtual link in GNS3 to simulate link degradation/failure.
        """
        pid = project_id or self.project_id
        if not pid or not link_id:
            return False
        try:
            resp = requests.put(
                f"{self.base_url}/projects/{pid}/links/{link_id}",
                json={"suspend": suspend},
                auth=self.auth,
                timeout=timeout or self.timeout
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            logger.error(f"Failed to set suspend={suspend} on link {link_id}: {e}")
            return False

    def start_node(self, node_id: str, project_id: Optional[str] = None, timeout: Optional[float] = None) -> bool:
        """Starts a specific node in GNS3."""
        pid = project_id or self.project_id
        if not pid or not node_id:
            return False
        try:
            resp = requests.post(f"{self.base_url}/projects/{pid}/nodes/{node_id}/start", auth=self.auth, timeout=timeout or self.timeout)
            return resp.status_code in (200, 201, 204)
        except Exception as e:
            logger.error(f"Failed to start node {node_id}: {e}")
            return False

    def start_all_nodes(self, project_id: Optional[str] = None, timeout: Optional[float] = None) -> bool:
        """Starts all nodes in the project."""
        pid = project_id or self.project_id
        if not pid:
            return False
        try:
            resp = requests.post(f"{self.base_url}/projects/{pid}/nodes/start", auth=self.auth, timeout=timeout or self.timeout)
            return resp.status_code in (200, 201, 204)
        except Exception as e:
            logger.error(f"Failed to start all nodes in {pid}: {e}")
            return False

    def stop_node(self, node_id: str, project_id: Optional[str] = None, timeout: Optional[float] = None) -> bool:
        """Stops a specific node in GNS3."""
        pid = project_id or self.project_id
        if not pid or not node_id:
            return False
        try:
            resp = requests.post(f"{self.base_url}/projects/{pid}/nodes/{node_id}/stop", auth=self.auth, timeout=timeout or self.timeout)
            return resp.status_code in (200, 201, 204)
        except Exception as e:
            logger.error(f"Failed to stop node {node_id}: {e}")
            return False

    def create_self_healing_topology(
        self,
        project_name: str = "AI-Self-Healing-Network"
    ) -> Dict[str, Any]:
        """
        Builds our required network topology in GNS3:
          Primary Path: R1 -> SW1 -> SW2 -> R2
          Backup Path:  R1 -> SW1 -> SW3 -> SW2 -> R2

        Uses available templates without requiring proprietary Cisco images.
        """
        projects = self.get_projects()
        target_proj = None
        for p in projects:
            if p.get("name") == project_name:
                target_proj = p
                break

        if not target_proj:
            target_proj = self.create_project(project_name)
            if not target_proj:
                return {
                    "success": False,
                    "message": f"Could not create GNS3 project '{project_name}'.",
                    "nodes": {},
                    "links": []
                }

        pid = target_proj.get("project_id")
        self.project_id = pid
        self.project_name = project_name

        # Open project if closed
        if target_proj.get("status") != "opened":
            self.open_project(pid)

        existing_nodes = {n.get("name"): n for n in self.get_nodes(pid)}

        # Coordinates for dark NOC layout
        desired_nodes = {
            "R1": {"type": "ethernet_switch", "x": 300, "y": 40},
            "SW1": {"type": "ethernet_switch", "x": 300, "y": 140},
            "SW2": {"type": "ethernet_switch", "x": 160, "y": 250},
            "SW3": {"type": "ethernet_switch", "x": 440, "y": 250},
            "R2": {"type": "ethernet_switch", "x": 160, "y": 360},
        }

        created_nodes = {}
        for name, spec in desired_nodes.items():
            if name in existing_nodes:
                created_nodes[name] = existing_nodes[name]
            else:
                n = self.create_node(name=name, node_type=spec["type"], x=spec["x"], y=spec["y"], project_id=pid)
                if n:
                    created_nodes[name] = n

        # Check links
        existing_links = self.get_links(pid)
        link_pairs = [
            ("R1", 0, "SW1", 0),  # Ingress link
            ("SW1", 1, "SW2", 0),  # Primary Link (SW1 -> SW2)
            ("SW1", 2, "SW3", 0),  # Backup Link Part 1 (SW1 -> SW3)
            ("SW3", 1, "SW2", 1),  # Backup Link Part 2 (SW3 -> SW2)
            ("SW2", 2, "R2", 0),  # Egress link (SW2 -> R2)
        ]

        # Determine existing connections between node IDs
        connected_pairs = set()
        for l in existing_links:
            nodes = l.get("nodes", [])
            if len(nodes) == 2:
                n1 = nodes[0].get("node_id")
                n2 = nodes[1].get("node_id")
                connected_pairs.add((n1, n2))
                connected_pairs.add((n2, n1))

        created_links = list(existing_links)
        for src_name, p1, dst_name, p2 in link_pairs:
            src_n = created_nodes.get(src_name)
            dst_n = created_nodes.get(dst_name)
            if src_n and dst_n:
                n1_id = src_n.get("node_id")
                n2_id = dst_n.get("node_id")
                if (n1_id, n2_id) not in connected_pairs:
                    lnk = self.create_link(n1_id, p1, n2_id, p2, project_id=pid)
                    if lnk:
                        created_links.append(lnk)
                        connected_pairs.add((n1_id, n2_id))
                        connected_pairs.add((n2_id, n1_id))

        return {
            "success": True,
            "project_id": pid,
            "project_name": project_name,
            "nodes": created_nodes,
            "links": created_links,
            "message": f"Topology built successfully in project '{project_name}' ({len(created_nodes)} nodes, {len(created_links)} links)."
        }

    def verify_topology(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Verifies whether the target project contains the required self-healing nodes
        (R1, SW1, SW2, SW3, R2) and valid primary/backup links.
        """
        pid = self._resolve_project_id(project_id)
        if not pid:
            return {
                "valid": False,
                "project_id": None,
                "missing_nodes": ["R1", "SW1", "SW2", "SW3", "R2"],
                "missing_links": ["Primary (SW1-SW2)", "Backup (SW1-SW3)", "Transit (SW3-SW2)"],
                "message": "No GNS3 project is currently selected."
            }

        nodes = self.get_nodes(pid)
        node_map = {n.get("name"): n for n in nodes}
        required_nodes = ["R1", "SW1", "SW2", "SW3", "R2"]
        missing_nodes = [rn for rn in required_nodes if rn not in node_map]

        links = self.get_links(pid)
        id_to_name = {n.get("node_id"): n.get("name") for n in nodes}

        connected_names = set()
        for l in links:
            l_nodes = l.get("nodes", [])
            if len(l_nodes) == 2:
                name1 = id_to_name.get(l_nodes[0].get("node_id"))
                name2 = id_to_name.get(l_nodes[1].get("node_id"))
                if name1 and name2:
                    connected_names.add((name1, name2))
                    connected_names.add((name2, name1))

        has_primary = ("SW1", "SW2") in connected_names
        has_backup_part1 = ("SW1", "SW3") in connected_names
        has_backup_part2 = ("SW3", "SW2") in connected_names

        missing_links = []
        if not has_primary:
            missing_links.append("Primary link (SW1 - SW2)")
        if not has_backup_part1:
            missing_links.append("Backup link part 1 (SW1 - SW3)")
        if not has_backup_part2:
            missing_links.append("Backup transit link (SW3 - SW2)")

        is_valid = (len(missing_nodes) == 0 and has_primary and has_backup_part1 and has_backup_part2)

        return {
            "valid": is_valid,
            "project_id": pid,
            "nodes": [
                {"name": n.get("name"), "status": n.get("status", "unknown"), "node_type": n.get("node_type")}
                for n in nodes
            ],
            "node_count": len(nodes),
            "link_count": len(links),
            "missing_nodes": missing_nodes,
            "missing_links": missing_links,
            "has_primary_path": has_primary,
            "has_backup_path": has_backup_part1 and has_backup_part2,
            "message": "Topology verified: All required nodes and paths exist." if is_valid else f"Topology incomplete: Missing {missing_nodes or missing_links}"
        }
