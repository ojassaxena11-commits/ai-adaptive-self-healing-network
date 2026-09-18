import random
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

class NetworkSimulator:
    """
    High-fidelity time-series network degradation simulator.
    Simulates multi-dimensional telemetry (RTT, jitter, packet loss, CRC errors,
    interface errors, flap counts, utilization) across 8 distinct operational scenarios.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.scenario: int = 1
        self.step_count: int = 0

        # Physical link state emulations
        self.primary_link_up: bool = True
        self.backup_link_up: bool = True
        self.primary_ospf_cost: int = 10
        self.backup_ospf_cost: int = 10

        # Stateful metric accumulators (so errors and trends build continuously over time)
        self.primary_crc_total: int = 0
        self.primary_err_total: int = 0
        self.primary_flaps: int = 0
        self.backup_crc_total: int = 0
        self.backup_err_total: int = 0
        self.backup_flaps: int = 0

        # Base noise levels
        self.base_rtt = 12.0
        self.base_jitter = 1.5
        self.base_util = 35.0

    def set_scenario(self, scenario_id: int) -> None:
        """Sets active experiment scenario (1 through 8)."""
        self.scenario = scenario_id
        self.step_count = 0

    def set_primary_cost(self, cost: int) -> None:
        """Simulates OSPF cost modification on SW1 GigabitEthernet0/1."""
        self.primary_ospf_cost = cost

    def set_primary_status(self, is_up: bool) -> None:
        """Simulates administrative or physical interface shutdown."""
        if self.primary_link_up != is_up:
            self.primary_flaps += 1
        self.primary_link_up = is_up

    def set_backup_status(self, is_up: bool) -> None:
        if self.backup_link_up != is_up:
            self.backup_flaps += 1
        self.backup_link_up = is_up

    def generate_telemetry_step(self) -> Dict[str, Dict[str, Any]]:
        """
        Advances simulation clock by 1 step (e.g. 1 second interval)
        and generates realistic continuous time-series metrics for Primary and Backup links.
        """
        self.step_count += 1
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # -------------------------------------------------------------
        # 1. Primary Link Telemetry Generation
        # -------------------------------------------------------------
        if not self.primary_link_up:
            # Complete physical failure
            p_rtt = 999.0
            p_jitter = 99.0
            p_loss = 100.0
            p_crc_inc = 0
            p_err_inc = 0
            p_util = 0.0
            p_status = "DOWN"
        else:
            p_status = "UP"
            if self.scenario == 1:
                # SCENARIO 1: Healthy Network
                p_rtt = max(8.0, self.base_rtt + random.gauss(0, 0.8))
                p_jitter = max(0.2, self.base_jitter + random.gauss(0, 0.3))
                p_loss = 0.0 if random.random() > 0.02 else 0.1
                p_crc_inc = 1 if random.random() < 0.05 else 0
                p_err_inc = p_crc_inc
                p_util = max(10.0, min(95.0, self.base_util + random.gauss(0, 3.0)))

            elif self.scenario == 2:
                # SCENARIO 2: Minor temporary jitter/spike (Noise below threshold)
                spike = 6.0 if 5 <= self.step_count <= 8 else 0.0
                p_rtt = max(8.0, self.base_rtt + spike + random.gauss(0, 1.0))
                p_jitter = max(0.5, self.base_jitter + (spike * 0.7) + random.gauss(0, 0.5))
                p_loss = 0.5 if spike > 0 else 0.0
                p_crc_inc = 1 if random.random() < 0.1 else 0
                p_err_inc = p_crc_inc
                p_util = max(10.0, min(95.0, self.base_util + random.gauss(0, 4.0)))

            elif self.scenario in (3, 4, 5):
                # SCENARIOS 3, 4, 5: Gradual severe physical degradation
                # Steps 1-4: normal, Steps 5-15: accelerating degradation
                deg_level = max(0, self.step_count - 4)
                p_rtt = self.base_rtt + (deg_level * 5.2) + random.gauss(0, 1.2)
                p_jitter = self.base_jitter + (deg_level * 2.8) + random.gauss(0, 0.6)
                p_loss = min(100.0, max(0.0, (deg_level * 1.6) + random.gauss(0, 0.4)))
                p_crc_inc = int(deg_level * 2.5 + random.randint(0, 2))
                p_err_inc = p_crc_inc + int(deg_level * 1.5)
                p_util = max(10.0, min(98.0, self.base_util + (deg_level * 3.5)))

                # Beyond step 18, link fails if not rerouted
                if self.step_count >= 18 and self.scenario == 4:
                    self.primary_link_up = False
                    p_status = "DOWN"
                    p_loss = 100.0

            elif self.scenario == 6:
                # SCENARIO 6: False Positive / Flapping burst
                burst = 18.0 if 4 <= self.step_count <= 7 else 0.0
                p_rtt = self.base_rtt + burst + random.gauss(0, 1.5)
                p_jitter = self.base_jitter + (burst * 0.5) + random.gauss(0, 0.8)
                p_loss = 2.0 if burst > 0 else 0.0
                p_crc_inc = 2 if burst > 0 else 0
                p_err_inc = p_crc_inc
                p_util = 40.0 + (burst * 1.5)

            elif self.scenario == 7:
                # SCENARIO 7: Primary Recovery & Hysteresis
                # Steps 1-5: down, Steps 6+: recovered and healthy
                if self.step_count < 6:
                    p_rtt = 999.0
                    p_jitter = 99.0
                    p_loss = 100.0
                    p_crc_inc = 0
                    p_err_inc = 0
                    p_util = 0.0
                    p_status = "DOWN"
                else:
                    p_status = "UP"
                    p_rtt = max(8.0, self.base_rtt + random.gauss(0, 0.8))
                    p_jitter = max(0.2, self.base_jitter + random.gauss(0, 0.3))
                    p_loss = 0.0
                    p_crc_inc = 0
                    p_err_inc = 0
                    p_util = 32.0

            elif self.scenario == 8:
                # SCENARIO 8: Primary normal, backup degrading
                p_rtt = max(8.0, self.base_rtt + random.gauss(0, 0.8))
                p_jitter = max(0.2, self.base_jitter + random.gauss(0, 0.3))
                p_loss = 0.0
                p_crc_inc = 0
                p_err_inc = 0
                p_util = 30.0

            else:
                p_rtt, p_jitter, p_loss, p_crc_inc, p_err_inc, p_util = 12.0, 1.5, 0.0, 0, 0, 35.0

        self.primary_crc_total += p_crc_inc
        self.primary_err_total += p_err_inc

        primary_record = {
            "timestamp": now_str,
            "device": "SW1",
            "interface": "GigabitEthernet0/1",
            "path_id": "PATH_PRIMARY",
            "rtt": round(p_rtt, 2),
            "jitter": round(p_jitter, 2),
            "packet_loss": round(p_loss, 2),
            "crc_errors": self.primary_crc_total,
            "interface_errors": self.primary_err_total,
            "interface_flaps": self.primary_flaps,
            "utilization": round(p_util, 2),
            "link_status": p_status,
            "ospf_cost": self.primary_ospf_cost,
            "telemetry_source": "SIMULATION"
        }

        # -------------------------------------------------------------
        # 2. Backup Link Telemetry Generation
        # -------------------------------------------------------------
        if not self.backup_link_up:
            b_rtt, b_jitter, b_loss, b_crc_inc, b_err_inc, b_util, b_status = 999.0, 99.0, 100.0, 0, 0, 0.0, "DOWN"
        else:
            b_status = "UP"
            if self.scenario == 5:
                # SCENARIO 5: Backup is poor / congested
                b_rtt = 65.0 + random.gauss(0, 4.0)
                b_jitter = 12.0 + random.gauss(0, 1.5)
                b_loss = 6.5 + random.gauss(0, 0.8)
                b_crc_inc = 3
                b_err_inc = 4
                b_util = 88.0 + random.gauss(0, 3.0)
            elif self.scenario == 8:
                # SCENARIO 8: Backup degrading
                deg = max(0, self.step_count - 3)
                b_rtt = 18.0 + (deg * 4.0)
                b_jitter = 2.0 + (deg * 1.8)
                b_loss = min(100.0, deg * 1.5)
                b_crc_inc = deg * 2
                b_err_inc = deg * 2
                b_util = 45.0 + (deg * 3.0)
            else:
                # Normal healthy backup (slightly higher base latency due to extra hop via SW3)
                b_rtt = max(14.0, 18.0 + random.gauss(0, 1.0))
                b_jitter = max(0.5, 2.0 + random.gauss(0, 0.4))
                b_loss = 0.0
                b_crc_inc = 0
                b_err_inc = 0
                b_util = 25.0 + random.gauss(0, 2.0)

        self.backup_crc_total += b_crc_inc
        self.backup_err_total += b_err_inc

        backup_record = {
            "timestamp": now_str,
            "device": "SW1",
            "interface": "GigabitEthernet0/2",
            "path_id": "PATH_BACKUP",
            "rtt": round(b_rtt, 2),
            "jitter": round(b_jitter, 2),
            "packet_loss": round(b_loss, 2),
            "crc_errors": self.backup_crc_total,
            "interface_errors": self.backup_err_total,
            "interface_flaps": self.backup_flaps,
            "utilization": round(b_util, 2),
            "link_status": b_status,
            "ospf_cost": self.backup_ospf_cost,
            "telemetry_source": "SIMULATION"
        }

        return {
            "primary": primary_record,
            "backup": backup_record
        }
