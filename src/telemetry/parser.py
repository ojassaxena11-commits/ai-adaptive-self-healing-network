import re
from typing import Dict, List, Any

class CiscoOutputParser:
    """Parses standard Cisco IOS CLI command outputs into structured Python dictionaries."""

    @staticmethod
    def parse_interface_brief(output: str) -> Dict[str, Dict[str, Any]]:
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
                    "is_up": (status == "up" and protocol == "up"),
                    "cost": 10
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
    def parse_interface_detail(output: str) -> Dict[str, Any]:
        """
        Parses detailed 'show interfaces GigabitEthernet0/1' output.
        Extracts MTU, BW, DLY, reliability, txload, rxload, input/output errors, CRC.
        """
        data: Dict[str, Any] = {
            "is_up": False,
            "line_protocol_up": False,
            "input_rate_bps": 0,
            "output_rate_bps": 0,
            "input_errors": 0,
            "crc_errors": 0,
            "output_errors": 0,
            "collisions": 0,
            "interface_resets": 0,
            "utilization": 25.0
        }

        if "is up, line protocol is up" in output:
            data["is_up"] = True
            data["line_protocol_up"] = True
        elif "is administratively down" in output or "is down" in output:
            data["is_up"] = False

        # Parse 5-minute input/output rates
        in_match = re.search(r"5 minute input rate (\d+) bits/sec", output)
        if in_match:
            data["input_rate_bps"] = int(in_match.group(1))

        out_match = re.search(r"5 minute output rate (\d+) bits/sec", output)
        if out_match:
            data["output_rate_bps"] = int(out_match.group(1))

        # Parse error counters
        err_match = re.search(r"(\d+) input errors,\s*(\d+) CRC", output)
        if err_match:
            data["input_errors"] = int(err_match.group(1))
            data["crc_errors"] = int(err_match.group(2))

        out_err_match = re.search(r"(\d+) output errors,\s*(\d+) collisions", output)
        if out_err_match:
            data["output_errors"] = int(out_err_match.group(1))
            data["collisions"] = int(out_err_match.group(2))

        # Utilization calculation approximation from BW/load if available
        load_match = re.search(r"txload (\d+)/255,\s*rxload (\d+)/255", output)
        if load_match:
            tx = int(load_match.group(1))
            rx = int(load_match.group(2))
            data["utilization"] = round(max(tx, rx) / 255.0 * 100.0, 1)

        return data

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
            r"O\s+(?:IA|E1|E2|N1|N2)?\s*(\d+\.\d+\.\d+\.\d+(?:/\d+)?)\s+\[(\d+)/(\d+)\]\s+via\s+(\d+\.\d+\.\d+\.\d+)(?:,\s*[0-9:]+)?,\s*([A-Za-z0-9/._-]+)"
        )
        for match in pattern.finditer(output):
            prefix, admin_dist, cost, next_hop, outgoing_intf = match.groups()
            routes.append({
                "prefix": prefix,
                "network": prefix,
                "admin_distance": int(admin_dist),
                "cost": int(cost),
                "next_hop": next_hop,
                "interface": outgoing_intf
            })
        return routes

    @staticmethod
    def parse_ospf_interface(output: str) -> Dict[str, Any]:
        """
        Parses output of 'show ip ospf interface GigabitEthernet0/1'.
        Extracts Cost, Process ID, Area, Network Type, State.
        """
        data = {
            "cost": 10,
            "process_id": 1,
            "area": "0",
            "state": "P2P"
        }
        cost_match = re.search(r"Cost:\s*(\d+)", output)
        if cost_match:
            data["cost"] = int(cost_match.group(1))

        area_match = re.search(r"Area\s*([0-9.]+)", output)
        if area_match:
            data["area"] = area_match.group(1)

        proc_match = re.search(r"Process ID\s*(\d+)", output)
        if proc_match:
            data["process_id"] = int(proc_match.group(1))

        state_match = re.search(r"State\s*([A-Za-z0-9/_-]+)", output)
        if state_match:
            data["state"] = state_match.group(1)

        return data

    @staticmethod
    def parse_ping_output(output: str) -> Dict[str, float]:
        """
        Parses output of Cisco IOS ping command:
        'Success rate is 100 percent (5/5), round-trip min/avg/max = 1/2/4 ms'
        """
        loss = 0.0
        rtt = 12.0
        jitter = 1.5

        succ_match = re.search(r"Success rate is (\d+) percent", output)
        if succ_match:
            loss = 100.0 - float(succ_match.group(1))

        rtt_match = re.search(r"round-trip min/avg/max = (\d+)/(\d+)/(\d+) ms", output)
        if rtt_match:
            min_r = float(rtt_match.group(1))
            avg_r = float(rtt_match.group(2))
            max_r = float(rtt_match.group(3))
            rtt = avg_r
            jitter = round(max_r - min_r, 2)

        return {
            "rtt": rtt,
            "jitter": jitter,
            "loss": loss,
            "packet_loss": loss
        }
