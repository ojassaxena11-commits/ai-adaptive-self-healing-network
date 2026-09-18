import os
import time
from typing import Dict, Any, List, Optional
from src.utils.logger import logger
from src.telemetry.parser import CiscoOutputParser

class CiscoController:
    """
    Unified Cisco Network Automation Controller.
    Supports Netmiko/SSH, CML REST API, and high-fidelity Simulated backend.
    Executes interface status discovery, OSPF neighbor tracking, and preemptive
    metric reconfiguration with strict DRY_RUN safety safeguards.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        raw_mode = self.config.get("mode") or os.getenv("ENV_MODE", "SIMULATION")
        self.mode = str(raw_mode).strip().upper()
        self.dry_run = self.config.get("decision", {}).get("dry_run", False)
        self.connected = False

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
            }
        }

        # Real SSH connections cache
        self.ssh_connections: Dict[str, Any] = {}

    def set_dry_run(self, dry_run: bool) -> None:
        self.dry_run = dry_run

    def connect(self) -> bool:
        """Establishes connection to CML or real devices via SSH."""
        raw_mode = self.config.get("mode") or os.getenv("ENV_MODE", "SIMULATION")
        self.mode = str(raw_mode).strip().upper()

        if self.mode == "SIMULATION":
            self.connected = True
            logger.info("CiscoController initialized in SIMULATION mode (CML connection disabled).")
            return True

        # CML / Real Device SSH Mode
        logger.info("Attempting live connection to Cisco devices via SSH/Netmiko (CML mode)...")
        try:
            from netmiko import ConnectHandler
            devices = self.config.get("network", {}).get("switches", {})
            username = os.getenv("CISCO_USERNAME", "admin")
            password = os.getenv("CISCO_PASSWORD", "cisco123!")

            # Try connecting to SW1
            sw1_ip = devices.get("SW1", {}).get("management_ip", "10.0.12.2")
            device_params = {
                "device_type": "cisco_ios",
                "host": sw1_ip,
                "username": username,
                "password": password,
                "timeout": 5,
            }
            conn = ConnectHandler(**device_params)
            self.ssh_connections["SW1"] = conn
            self.connected = True
            logger.info(f"Successfully connected to SW1 at {sw1_ip} via SSH.")
            return True
        except Exception as e:
            logger.warning(f"Could not connect to live Cisco device ({e}). CML is offline / unreachable.")
            self.connected = False
            return False

    def is_connected(self) -> bool:
        if self.mode == "SIMULATION":
            return True
        return self.connected and bool(self.ssh_connections)

    def get_interface_status(self, device: str = "SW1") -> Dict[str, Any]:
        """Queries interface up/down status."""
        if self.mode == "CML" and device in self.ssh_connections:
            try:
                output = self.ssh_connections[device].send_command("show ip interface brief")
                return CiscoOutputParser.parse_interface_brief(output)
            except Exception as e:
                logger.error(f"Error querying {device} via SSH: {e}")

        # Fallback simulated state
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
                # Parse standard Cisco ping output: 'Success rate is 100 percent (5/5), round-trip min/avg/max = 1/2/4 ms'
                import re
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

        if self.dry_run:
            logger.warning(f"[DRY_RUN ACTIVE] Would configure on {device}: {cmd_str}")
            return True

        logger.info(f"[ROUTING ACTION] Executing on {device}: {cmd_str}")

        if self.mode == "CML" and device in self.ssh_connections:
            try:
                output = self.ssh_connections[device].send_config_set(cisco_cmds)
                logger.info(f"Cisco CLI execution response:\n{output}")
                return True
            except Exception as e:
                logger.error(f"Failed to configure {device} via SSH: {e}")
                return False

        # Simulated state mutation
        if device in self.simulated_interfaces and interface in self.simulated_interfaces[device]:
            self.simulated_interfaces[device][interface]["cost"] = new_cost
            logger.info(f"Simulated {device} {interface} OSPF cost updated to {new_cost}")
            return True
        return False

    def restore_metric(self, device: str = "SW1", interface: str = "GigabitEthernet0/1", original_cost: int = 10) -> bool:
        """Restores baseline OSPF cost upon link recovery."""
        return self.change_metric(device=device, interface=interface, new_cost=original_cost)

    def shutdown_interface(self, device: str = "SW1", interface: str = "GigabitEthernet0/1") -> bool:
        """Injects physical link failure via interface shutdown."""
        cisco_cmds = [f"interface {interface}", "shutdown", "end"]
        if self.dry_run:
            logger.warning(f"[DRY_RUN ACTIVE] Would shutdown {device} {interface}")
            return True

        logger.warning(f"[FAILURE INJECTION] Shutting down {device} {interface}")
        if self.mode == "CML" and device in self.ssh_connections:
            try:
                self.ssh_connections[device].send_config_set(cisco_cmds)
                return True
            except Exception as e:
                logger.error(f"Error shutting down {device} {interface}: {e}")
                return False

        if device in self.simulated_interfaces and interface in self.simulated_interfaces[device]:
            self.simulated_interfaces[device][interface]["is_up"] = False
            return True
        return False

    def enable_interface(self, device: str = "SW1", interface: str = "GigabitEthernet0/1") -> bool:
        """Restores physical link via interface 'no shutdown'."""
        cisco_cmds = [f"interface {interface}", "no shutdown", "end"]
        if self.dry_run:
            logger.warning(f"[DRY_RUN ACTIVE] Would enable {device} {interface}")
            return True

        logger.info(f"[RECOVERY INJECTION] Bringing up {device} {interface}")
        if self.mode == "CML" and device in self.ssh_connections:
            try:
                self.ssh_connections[device].send_config_set(cisco_cmds)
                return True
            except Exception as e:
                logger.error(f"Error enabling {device} {interface}: {e}")
                return False

        if device in self.simulated_interfaces and interface in self.simulated_interfaces[device]:
            self.simulated_interfaces[device][interface]["is_up"] = True
            return True
        return False
