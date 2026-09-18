import re
from typing import Dict, List, Any

class CiscoOutputParser:
    """Parses standard Cisco IOS CLI command outputs into structured Python dictionaries."""

    @staticmethod
    def parse_interface_brief(output: str) -> Dict[str, Dict[str, str]]:
        """
        Parses output of 'show ip interface brief'.
        Example line:
        GigabitEthernet0/1     10.0.23.1       YES manual up                    up
        """
        interfaces = {}
        for line in output.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("Interface") or line.startswith("---"):
                continue
            parts = re.split(r"\s+", line)
            if len(parts) >= 6:
                intf_name = parts[0]
                ip_addr = parts[1]
                status = parts[4].lower()
                protocol = parts[5].lower()
                interfaces[intf_name] = {
                    "ip_address": ip_addr,
                    "status": status,
                    "protocol": protocol,
                    "is_up": (status == "up" and protocol == "up")
                }
        return interfaces

    @staticmethod
    def parse_counters_errors(output: str) -> Dict[str, Dict[str, int]]:
        """
        Parses output of 'show interfaces counters errors'.
        Extracts CRC Align-Err, FCS-Err, Xmit-Err, Rcv-Err.
        """
        errors = {}
        for line in output.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("Port") or line.startswith("---"):
                continue
            parts = re.split(r"\s+", line)
            if len(parts) >= 6:
                port = parts[0]
                try:
                    align_err = int(parts[1])
                    fcs_err = int(parts[2])
                    xmit_err = int(parts[3])
                    rcv_err = int(parts[4])
                    errors[port] = {
                        "align_err": align_err,
                        "fcs_crc_err": fcs_err,
                        "xmit_err": xmit_err,
                        "rcv_err": rcv_err,
                        "total_errors": align_err + fcs_err + xmit_err + rcv_err
                    }
                except ValueError:
                    continue
        return errors

    @staticmethod
    def parse_ospf_neighbors(output: str) -> List[Dict[str, Any]]:
        """
        Parses output of 'show ip ospf neighbor'.
        Example line:
        22.22.22.22       1   FULL/BDR        00:00:34    10.0.23.2       GigabitEthernet0/1
        """
        neighbors = []
        for line in output.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("Neighbor") or line.startswith("---"):
                continue
            parts = re.split(r"\s+", line)
            if len(parts) >= 6:
                neighbor_id = parts[0]
                state_field = parts[2]
                state = state_field.split("/")[0]
                role = state_field.split("/")[1] if "/" in state_field else "UNKNOWN"
                ip_addr = parts[4]
                interface = parts[5]
                neighbors.append({
                    "neighbor_id": neighbor_id,
                    "state": state,
                    "role": role,
                    "ip_address": ip_addr,
                    "interface": interface,
                    "is_full": (state == "FULL")
                })
        return neighbors

    @staticmethod
    def parse_ip_route_ospf(output: str) -> List[Dict[str, Any]]:
        """
        Parses output of 'show ip route ospf'.
        Example line:
        O   192.168.2.0/24 [110/30] via 10.0.23.2, 00:05:12, GigabitEthernet0/1
        """
        routes = []
        pattern = re.compile(
            r"O\s+(?:IA|E1|E2|N1|N2)?\s*(\d+\.\d+\.\d+\.\d+(?:/\d+)?)\s+\[(\d+)/(\d+)\]\s+via\s+(\d+\.\d+\.\d+\.\d+).*?,\s*([A-Za-z0-9/]+)"
        )
        for match in pattern.finditer(output):
            prefix, admin_dist, cost, next_hop, outgoing_intf = match.groups()
            routes.append({
                "prefix": prefix,
                "admin_distance": int(admin_dist),
                "cost": int(cost),
                "next_hop": next_hop,
                "interface": outgoing_intf
            })
        return routes
