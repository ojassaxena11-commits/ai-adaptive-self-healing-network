import os
import csv
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd

from src.utils.logger import logger
from src.telemetry.simulator import NetworkSimulator
from src.telemetry.parser import CiscoOutputParser

class TelemetryCollector:
    """
    Unified Network Telemetry Collector.
    Polls real network devices via SSH / CML REST API or falls back gracefully
    to the high-fidelity simulator, outputting standardized multi-dimensional records.
    """

    CSV_HEADER = [
        "timestamp", "device", "interface", "path_id", "rtt", "jitter",
        "packet_loss", "crc_errors", "interface_errors", "input_errors",
        "output_errors", "interface_flaps", "utilization", "link_status",
        "ospf_cost", "telemetry_source"
    ]

    def __init__(self, config: Dict[str, Any], cisco_controller: Optional[Any] = None):
        self.config = config
        self.mode = config.get("mode", "SIMULATION").upper()
        self.cisco_controller = cisco_controller
        self.storage_path = config.get("telemetry", {}).get("storage_path", "data/telemetry.csv")
        self.buffer_size = config.get("telemetry", {}).get("history_buffer_size", 100)

        # Simulator instance for SIMULATION mode or fallback
        self.simulator = NetworkSimulator(config)

        # In-memory history buffer (list of dicts)
        self.history_buffer: List[Dict[str, Any]] = []

        # Ensure directory exists and initialize CSV file
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path) or os.path.getsize(self.storage_path) == 0:
            with open(self.storage_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADER)

    def set_mode(self, mode: str) -> None:
        """Dynamically switches collection backend between SIMULATION and CML."""
        self.mode = mode.strip().upper()
        self.config["mode"] = self.mode

    def set_scenario(self, scenario_id: int) -> None:
        """Sets scenario on underlying simulator."""
        self.simulator.set_scenario(scenario_id)

    def collect_step(self) -> Dict[str, Dict[str, Any]]:
        """
        Executes one telemetry collection polling cycle.
        Returns a dictionary containing normalized 'primary' and 'backup' records.
        """
        records: Dict[str, Dict[str, Any]] = {}

        if self.mode == "CML" and self.cisco_controller and self.cisco_controller.is_connected():
            try:
                records = self._collect_from_live_cml()
            except Exception as e:
                logger.warning(f"Live CML telemetry collection failed: {e}. Falling back to simulation.")
                records = self._collect_from_simulator()
        else:
            records = self._collect_from_simulator()

        # Normalize and append to buffer and CSV
        for key in ["primary", "backup"]:
            rec = records[key]
            # Ensure all schema keys are present
            rec.setdefault("input_errors", rec.get("interface_errors", 0))
            rec.setdefault("output_errors", 0)
            self.history_buffer.append(rec)
            self._append_csv(rec)

        # Trim buffer
        if len(self.history_buffer) > (self.buffer_size * 2):
            self.history_buffer = self.history_buffer[-(self.buffer_size * 2):]

        return records

    def _collect_from_simulator(self) -> Dict[str, Dict[str, Any]]:
        """Generates synthetic telemetry from simulator."""
        raw = self.simulator.generate_telemetry_step()
        for k in ["primary", "backup"]:
            raw[k].setdefault("input_errors", raw[k].get("interface_errors", 0))
            raw[k].setdefault("output_errors", 0)
        return raw

    def _collect_from_live_cml(self) -> Dict[str, Dict[str, Any]]:
        """
        Polls live Cisco devices via the cisco_controller.
        Combines real interface error counters and ping latency probes.
        """
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Query SW1 interface counters
        sw1_intfs = self.cisco_controller.get_interface_status("SW1")
        sw1_errors = self.cisco_controller.get_interface_errors("SW1")
        ping_res = self.cisco_controller.measure_rtt("R1", "192.168.2.1")

        p_intf = sw1_intfs.get("GigabitEthernet0/1", {})
        p_up = p_intf.get("is_up", True)
        p_cost = p_intf.get("cost", 10)
        p_err = sw1_errors.get("Gi0/1", {})

        primary_record = {
            "timestamp": now_str,
            "device": "SW1",
            "interface": "GigabitEthernet0/1",
            "path_id": "PATH_PRIMARY",
            "rtt": ping_res.get("rtt", 12.0),
            "jitter": ping_res.get("jitter", 1.5),
            "packet_loss": ping_res.get("loss", 0.0),
            "crc_errors": p_err.get("fcs_crc_err", 0),
            "interface_errors": p_err.get("total_errors", 0),
            "input_errors": p_err.get("rcv_err", 0),
            "output_errors": p_err.get("xmit_err", 0),
            "interface_flaps": 0,
            "utilization": 42.0,
            "link_status": "UP" if p_up else "DOWN",
            "ospf_cost": p_cost,
            "telemetry_source": "REAL_CML"
        }

        b_intf = sw1_intfs.get("GigabitEthernet0/2", {})
        b_up = b_intf.get("is_up", True)
        b_cost = b_intf.get("cost", 10)
        b_err = sw1_errors.get("Gi0/2", {})

        backup_record = {
            "timestamp": now_str,
            "device": "SW1",
            "interface": "GigabitEthernet0/2",
            "path_id": "PATH_BACKUP",
            "rtt": 18.0,
            "jitter": 2.1,
            "packet_loss": 0.0,
            "crc_errors": b_err.get("fcs_crc_err", 0),
            "interface_errors": b_err.get("total_errors", 0),
            "input_errors": b_err.get("rcv_err", 0),
            "output_errors": b_err.get("xmit_err", 0),
            "interface_flaps": 0,
            "utilization": 22.0,
            "link_status": "UP" if b_up else "DOWN",
            "ospf_cost": b_cost,
            "telemetry_source": "REAL_CML"
        }

        return {"primary": primary_record, "backup": backup_record}

    def _append_csv(self, record: Dict[str, Any]) -> None:
        """Appends a single telemetry record to disk."""
        try:
            with open(self.storage_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([record.get(col, "") for col in self.CSV_HEADER])
        except Exception as e:
            logger.error(f"Failed writing telemetry to {self.storage_path}: {e}")

    def get_recent_history(self, path_id: Optional[str] = None, n_samples: int = 20) -> pd.DataFrame:
        """Returns recent telemetry as a pandas DataFrame, optionally filtered by path."""
        if not self.history_buffer:
            return pd.DataFrame(columns=self.CSV_HEADER)

        df = pd.DataFrame(self.history_buffer)
        if path_id:
            df = df[df["path_id"] == path_id]
        return df.tail(n_samples)
