import os
import re
import time
from typing import Dict, Any, List, Optional
from src.utils.logger import logger
from src.telemetry.parser import CiscoOutputParser
from src.cml.cml_client import CMLClient

class CiscoController:
    """
    Unified Cisco Network Automation Controller.
    Supports Netmiko/SSH, CML REST API, and high-fidelity Simulated backend.
    Executes interface status discovery, OSPF neighbor tracking, preemptive
    metric reconfiguration with strict DRY_RUN safety safeguards, and
    post-reroute routing table verification.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        raw_mode = self.config.get("mode") or os.getenv("ENV_MODE", "SIMULATION")
        self.mode = str(raw_mode).strip().upper()
        self.dry_run = self.config.get("decision", {}).get("dry_run", False)
        self.connected = False

        # CML REST API Client
        self.cml_client = CMLClient(self.config)

        # Simulated state tracking
        self.simulated_interfaces = {
            "SW1": {
                "GigabitEthernet0/0": {"is_up": True, "ip": "10.0.12.2", "cost": 10},
                "GigabitEthernet0/1": {"is_up": True, "ip": "10.0.23.1", "cost": 10},
                "GigabitEthernet0/2": {"is_up": True, "ip": "10.0.13.1", "cost": 10},
            },
            "SW2": {
                "GigabitEthernet0/1": {"is_up": True, "ip": "10.0.23.2", "cost": 10},
                "GigabitEthernet0/2": {"is_up": True, "ip": "10.0.32.2", "cost": 10},
                "GigabitEthernet0/0": {"is_up": True, "ip": "10.0.24.1", "cost": 10},
            },
            "SW3": {
                "GigabitEthernet0/2": {"is_up": True, "ip": "10.0.13.2", "cost": 10},
                "GigabitEthernet0/1": {"is_up": True, "ip": "10.0.32.1", "cost": 10},
            }
        }

        # Real SSH connections cache
        self.ssh_connections: Dict[str, Any] = {}

        # Audit history of executed / dry-run commands
        self.action_history: List[Dict[str, Any]] = []
        self.last_action: Optional[Dict[str, Any]] = None

    def set_mode(self, mode: str) -> None:
        """Dynamically switches operational backend between SIMULATION and CML."""
        self.mode = mode.strip().upper()
        self.config["mode"] = self.mode
        if self.mode == "SIMULATION":
            self.connected = True
        else:
            self.connected = False

    def set_dry_run(self, dry_run: bool) -> None:
        """Sets safe dry-run mode."""
        self.dry_run = dry_run

    def connect(self) -> bool:
        """Establishes connection to CML or real devices via SSH."""
        raw_mode = self.config.get("mode") or os.getenv("ENV_MODE", "SIMULATION")
        self.mode = str(raw_mode).strip().upper()

        if self.mode == "SIMULATION":
            self.connected = True
            logger.info("CiscoController initialized in SIMULATION mode (CML connection disabled).")
            return True

        # CML Mode: Test CML REST API + SSH to devices
        logger.info("Attempting live connection to Cisco CML and switch infrastructure...")
        cml_status = self.cml_client.test_connectivity()

        try:
            from netmiko import ConnectHandler
            devices = self.config.get("network", {}).get("switches", {})
            username = os.getenv("CISCO_USERNAME", "admin")
            password = os.getenv("CISCO_PASSWORD", "")
            port = int(os.getenv("CISCO_PORT", "22"))

            sw1_ip = devices.get("SW1", {}).get("management_ip", "10.0.12.2")
            device_params = {
                "device_type": "cisco_ios",
                "host": sw1_ip,
                "port": port,
                "username": username,
                "password": password,
                "timeout": 4,
            }
            conn = ConnectHandler(**device_params)
            self.ssh_connections["SW1"] = conn
            self.connected = True
            logger.info(f"Successfully connected to SW1 at {sw1_ip} via SSH.")
            return True
        except Exception as e:
            # If Netmiko connection fails, check if CML REST API succeeded
            if cml_status.get("status") == CMLClient.STATUS_CONNECTED:
                self.connected = True
                logger.info("Connected to CML Controller via REST API (SSH nodes pending).")
                return True

            logger.warning(f"Could not connect to live Cisco device ({e}). CML is offline / unreachable.")
            self.connected = False
            return False

    def is_connected(self) -> bool:
        if self.mode == "SIMULATION":
            return True
        return self.connected and (bool(self.ssh_connections) or self.cml_client.status == CMLClient.STATUS_CONNECTED)

    def verify_cml_connection(self) -> Dict[str, Any]:
        """
        Executes a diagnostic check across both CML REST API and device SSH.
        Returns detailed status suitable for presentation in the GUI.
        """
        rest_check = self.cml_client.test_connectivity()
        devices = self.config.get("network", {}).get("switches", {})
        sw1_ip = devices.get("SW1", {}).get("management_ip", "10.0.12.2")

        ssh_status = {
            "SW1": {"ip": sw1_ip, "connected": "SW1" in self.ssh_connections, "status": "UP" if "SW1" in self.ssh_connections else "OFFLINE"},
            "SW2": {"ip": "10.0.24.1", "connected": "SW2" in self.ssh_connections, "status": "UP" if "SW2" in self.ssh_connections else "OFFLINE"},
            "SW3": {"ip": "10.0.13.2", "connected": "SW3" in self.ssh_connections, "status": "UP" if "SW3" in self.ssh_connections else "OFFLINE"}
        }

        # Overall status evaluation
        if not self.cml_client.is_configured():
            overall = CMLClient.STATUS_NOT_CONFIGURED
            msg = "CML parameters not configured in .env. Using default simulation mode."
        elif rest_check.get("status") == CMLClient.STATUS_CONNECTED:
            overall = CMLClient.STATUS_CONNECTED
            msg = f"CML Connected: Controller reachable at {self.cml_client.host}:{self.cml_client.port} (Lab: {self.cml_client.lab_id})."
        else:
            overall = CMLClient.STATUS_ERROR
            msg = rest_check.get("message", "CML host is unreachable.")

        return {
            "status": overall,
            "cml_rest": rest_check,
            "ssh_devices": ssh_status,
            "message": msg,
            "timestamp": time.strftime("%H:%M:%S")
        }

    def get_interface_status(self, device: str = "SW1") -> Dict[str, Any]:
        """Queries interface up/down status."""
        if self.mode == "CML" and device in self.ssh_connections:
            try:
                output = self.ssh_connections[device].send_command("show ip interface brief")
                return CiscoOutputParser.parse_interface_brief(output)
            except Exception as e:
                logger.error(f"Error querying {device} via SSH: {e}")

        # Return simulated interface state
        return self.simulated_interfaces.get(device, {})

    def get_interface_errors(self, device: str = "SW1") -> Dict[str, Any]:
        """Queries hardware error counters."""
        if self.mode == "CML" and device in self.ssh_connections:
            try:
                output = self.ssh_connections[device].send_command("show interfaces counters errors")
                return CiscoOutputParser.parse_counters_errors(output)
            except Exception as e:
                logger.error(f"Error querying counters on {device}: {e}")

        return {
            "Gi0/1": {"align_err": 0, "fcs_crc_err": 0, "xmit_err": 0, "rcv_err": 0, "total_errors": 0},
            "Gi0/2": {"align_err": 0, "fcs_crc_err": 0, "xmit_err": 0, "rcv_err": 0, "total_errors": 0}
        }

    def get_ospf_state(self, device: str = "SW1") -> List[Dict[str, Any]]:
        """Queries OSPF neighbors and adjacency state."""
        if self.mode == "CML" and device in self.ssh_connections:
            try:
                output = self.ssh_connections[device].send_command("show ip ospf neighbor")
                return CiscoOutputParser.parse_ospf_neighbors(output)
            except Exception as e:
                logger.error(f"Error querying OSPF state on {device}: {e}")

        # Simulated OSPF state
        return [
            {"neighbor_id": "22.22.22.22", "state": "FULL", "interface": "GigabitEthernet0/1", "is_full": True},
            {"neighbor_id": "33.33.33.33", "state": "FULL", "interface": "GigabitEthernet0/2", "is_full": True},
        ]

    def measure_rtt(self, source_device: str, target_ip: str) -> Dict[str, float]:
        """Measures RTT and loss to destination IP."""
        if self.mode == "CML" and source_device in self.ssh_connections:
            try:
                output = self.ssh_connections[source_device].send_command(f"ping {target_ip} repeat 5 timeout 1")
                loss = 0.0
                rtt = 12.0
                match_succ = re.search(r"Success rate is (\d+) percent", output)
                if match_succ:
                    loss = 100.0 - float(match_succ.group(1))
                match_rtt = re.search(r"round-trip min/avg/max = (\d+)/(\d+)/(\d+) ms", output)
                if match_rtt:
                    rtt = float(match_rtt.group(2))
                return {"rtt": rtt, "jitter": 1.2, "loss": loss}
            except Exception as e:
                logger.error(f"Ping execution error from {source_device}: {e}")

        return {"rtt": 12.0, "jitter": 1.5, "loss": 0.0}

    def change_metric(self, device: str = "SW1", interface: str = "GigabitEthernet0/1", new_cost: int = 100) -> bool:
        """
        Modifies OSPF link cost on specified interface.
        Enforces DRY_RUN verification before modifying state.
        """
        cisco_cmds = [
            f"interface {interface}",
            f"ip ospf cost {new_cost}",
            "end"
        ]
        cmd_str = " -> ".join(cisco_cmds)

        record = {
            "timestamp": time.strftime("%H:%M:%S"),
            "device": device,
            "interface": interface,
            "action": "CHANGE_METRIC",
            "new_cost": new_cost,
            "commands": cisco_cmds,
            "command_str": cmd_str,
            "dry_run": self.dry_run,
            "executed": not self.dry_run,
            "success": True,
            "output": ""
        }

        if self.dry_run:
            logger.warning(f"[DRY_RUN ACTIVE] Would configure on {device}: {cmd_str}")
            self.last_action = record
            self.action_history.append(record)
            return True

        logger.info(f"[ROUTING ACTION] Executing on {device}: {cmd_str}")

        if self.mode == "CML" and device in self.ssh_connections:
            try:
                output = self.ssh_connections[device].send_config_set(cisco_cmds)
                logger.info(f"Cisco CLI execution response:\n{output}")
                record["output"] = output
                self.last_action = record
                self.action_history.append(record)
                return True
            except Exception as e:
                logger.error(f"Failed to configure {device} via SSH: {e}")
                record["success"] = False
                record["output"] = str(e)
                self.last_action = record
                self.action_history.append(record)
                return False

        # Simulated state mutation
        if device in self.simulated_interfaces and interface in self.simulated_interfaces[device]:
            self.simulated_interfaces[device][interface]["cost"] = new_cost
            logger.info(f"Simulated {device} {interface} OSPF cost updated to {new_cost}")
            self.last_action = record
            self.action_history.append(record)
            return True
        return False

    def restore_metric(self, device: str = "SW1", interface: str = "GigabitEthernet0/1", original_cost: int = 10) -> bool:
        """Restores baseline OSPF cost upon link recovery."""
        return self.change_metric(device=device, interface=interface, new_cost=original_cost)

    def shutdown_interface(self, device: str = "SW1", interface: str = "GigabitEthernet0/1") -> bool:
        """Injects physical link failure via interface shutdown."""
        cisco_cmds = [f"interface {interface}", "shutdown", "end"]
        cmd_str = " -> ".join(cisco_cmds)

        record = {
            "timestamp": time.strftime("%H:%M:%S"),
            "device": device,
            "interface": interface,
            "action": "SHUTDOWN_INTERFACE",
            "commands": cisco_cmds,
            "command_str": cmd_str,
            "dry_run": self.dry_run,
            "executed": not self.dry_run,
            "success": True
        }

        if self.dry_run:
            logger.warning(f"[DRY_RUN ACTIVE] Would shutdown {device} {interface}")
            self.last_action = record
            self.action_history.append(record)
            return True

        logger.warning(f"[FAILURE INJECTION] Shutting down {device} {interface}")
        if self.mode == "CML" and device in self.ssh_connections:
            try:
                output = self.ssh_connections[device].send_config_set(cisco_cmds)
                record["output"] = output
                self.last_action = record
                self.action_history.append(record)
                return True
            except Exception as e:
                logger.error(f"Error shutting down {device} {interface}: {e}")
                record["success"] = False
                record["output"] = str(e)
                self.last_action = record
                self.action_history.append(record)
                return False

        if device in self.simulated_interfaces and interface in self.simulated_interfaces[device]:
            self.simulated_interfaces[device][interface]["is_up"] = False
            self.last_action = record
            self.action_history.append(record)
            return True
        return False

    def enable_interface(self, device: str = "SW1", interface: str = "GigabitEthernet0/1") -> bool:
        """Restores physical link via interface 'no shutdown'."""
        cisco_cmds = [f"interface {interface}", "no shutdown", "end"]
        cmd_str = " -> ".join(cisco_cmds)

        record = {
            "timestamp": time.strftime("%H:%M:%S"),
            "device": device,
            "interface": interface,
            "action": "ENABLE_INTERFACE",
            "commands": cisco_cmds,
            "command_str": cmd_str,
            "dry_run": self.dry_run,
            "executed": not self.dry_run,
            "success": True
        }

        if self.dry_run:
            logger.warning(f"[DRY_RUN ACTIVE] Would enable {device} {interface}")
            self.last_action = record
            self.action_history.append(record)
            return True

        logger.info(f"[RECOVERY INJECTION] Bringing up {device} {interface}")
        if self.mode == "CML" and device in self.ssh_connections:
            try:
                output = self.ssh_connections[device].send_config_set(cisco_cmds)
                record["output"] = output
                self.last_action = record
                self.action_history.append(record)
                return True
            except Exception as e:
                logger.error(f"Error enabling {device} {interface}: {e}")
                record["success"] = False
                record["output"] = str(e)
                self.last_action = record
                self.action_history.append(record)
                return False

        if device in self.simulated_interfaces and interface in self.simulated_interfaces[device]:
            self.simulated_interfaces[device][interface]["is_up"] = True
            self.last_action = record
            self.action_history.append(record)
            return True
        return False

    def verify_routing(self, device: str = "SW1") -> Dict[str, Any]:
        """
        Queries OSPF routing table on device and verifies whether traffic
        has dynamically converged to the redundant backup path via SW3.
        """
        if self.mode == "CML" and device in self.ssh_connections:
            try:
                output = self.ssh_connections[device].send_command("show ip route ospf")
                routes = CiscoOutputParser.parse_ip_route_ospf(output)
                # Check route to destination 192.168.2.0/24 or transit
                active_via_backup = any(
                    "Gi0/2" in r.get("interface", "") or "10.0.13" in r.get("next_hop", "")
                    for r in routes
                )
                return {
                    "verified": True,
                    "traffic_migrated": active_via_backup,
                    "active_path": "R1 → SW1 → SW3 → SW2 → R2" if active_via_backup else "R1 → SW1 → SW2 → R2",
                    "routes": routes,
                    "details": "OSPF converged to SW3 transit path." if active_via_backup else "OSPF utilizing primary direct path."
                }
            except Exception as e:
                logger.error(f"Failed verifying routing on {device}: {e}")

        # Simulated verification check
        sw1_cost = self.simulated_interfaces.get("SW1", {}).get("GigabitEthernet0/1", {}).get("cost", 10)
        p_up = self.simulated_interfaces.get("SW1", {}).get("GigabitEthernet0/1", {}).get("is_up", True)

        rerouted = (sw1_cost >= 100 or not p_up)
        return {
            "verified": True,
            "traffic_migrated": rerouted,
            "active_path": "R1 → SW1 → SW3 → SW2 → R2" if rerouted else "R1 → SW1 → SW2 → R2",
            "primary_cost": sw1_cost,
            "backup_cost": 10,
            "details": f"OSPF cost modified to {sw1_cost}. Traffic diverted via Backup Path (SW3)." if rerouted else "Baseline OSPF metric active. Optimal primary path selected."
        }
