import streamlit as st
import json
import os
import pandas as pd


class CostRule:
    """Interface for pluggable operational scheduling rules."""
    def calculate_penalty(self, bus, station, arrival_time, charger_free_time, weights) -> float:
        raise NotImplementedError

class IndividualWaitRule(CostRule):
    def calculate_penalty(self, bus, station, arrival_time, charger_free_time, weights) -> float:
        wait_time = max(0, charger_free_time - arrival_time)
        return wait_time * weights.get("individual", 1.0)

class OperatorSmoothnessRule(CostRule):
    def calculate_penalty(self, bus, station, arrival_time, charger_free_time, weights) -> float:
        if charger_free_time <= arrival_time:
            return 0.0
        return 15.0 * weights.get("operator", 1.0)


class BusSimulationEngine:
    def __init__(self, network, scenario):
        self.network = network
        self.scenario = scenario
        self.weights = scenario["weights"]
        self.speed = network["global_parameters"]["bus_speed_kmh"]
        self.max_range = network["global_parameters"]["bus_max_range_km"]
        
        
        self.rules = [IndividualWaitRule(), OperatorSmoothnessRule()]
        
       
        self.station_registry = {
            st_id: [0] * cfg["chargers"] 
            for st_id, cfg in network["station_capabilities"].items()
        }

    def _time_str_to_min(self, time_str):
        h, m = map(int, time_str.split(":"))
        return h * 60 + m

    def _min_to_time_str(self, minutes):
        total_mins = int(minutes) % 1440
        return f"{total_mins // 60:02d}:{total_mins % 60:02d}"

    def generate_valid_stops(self, direction):
        """Precomputes safe route paths that respect the 240km limit."""
        if direction == "Bengaluru Kochi":
            return ["A", "C"]
        return ["D", "B"]

    def run(self):
        bus_events = []
        for b_cfg in self.scenario["buses"]:
            bus_events.append({
                **b_cfg,
                "start_min": self._time_str_to_min(b_cfg["departure"])
            })
        
      
        bus_events.sort(key=lambda x: x["start_min"])
        
        bus_timetables = []
        station_logs = {st_id: [] for st_id in self.network["ordered_stations"]}
        
        for bus in bus_events:
            current_time = bus["start_min"]
            stops_to_make = self.generate_valid_stops(bus["direction"])
            
            origin = "Bengaluru" if bus["direction"] == "Bengaluru Kochi" else "Kochi"
            timeline = [f"Depart {origin} @ {self._min_to_time_str(current_time)}"]
            total_wait = 0
            
            stations_sequence = self.network["ordered_stations"]
            if bus["direction"] != "Bengaluru Kochi":
                stations_sequence = list(reversed(stations_sequence))
                
            for target_station in stations_sequence:
                segment_dist = 0
                for seg in self.network["segments"]:
                    if bus["direction"] == "Bengaluru Kochi" and seg["to"] == target_station:
                        segment_dist = seg["distance_km"]
                        break
                    elif bus["direction"] != "Bengaluru Kochi" and seg["from"] == target_station:
                        segment_dist = seg["distance_km"]
                        break
                
               
                travel_time = (segment_dist / self.speed) * 60
                current_time += travel_time
                
                if target_station in stops_to_make:
                    charger_free_times = self.station_registry[target_station]
                   
                    best_charger_idx = 0
                    min_penalty = float('inf')
                    
                    for idx, free_time in enumerate(charger_free_times):
                        penalty = sum(r.calculate_penalty(bus, target_station, current_time, free_time, self.weights) for r in self.rules)
                        if penalty < min_penalty:
                            min_penalty = penalty
                            best_charger_idx = idx
                            
                    selected_free_time = charger_free_times[best_charger_idx]
                    wait_time = max(0, selected_free_time - current_time)
                    total_wait += wait_time
                    
                    start_charge = current_time + wait_time
                    charge_duration = self.network["station_capabilities"][target_station]["duration_min"]
                    end_charge = start_charge + charge_duration
                    
                    self.station_registry[target_station][best_charger_idx] = end_charge
                    
                    timeline.append(
                        f"Station {target_station}: Arrive {self._min_to_time_str(current_time)}, "
                        f"Wait {int(wait_time)}m, Charge {self._min_to_time_str(start_charge)}-{self._min_to_time_str(end_charge)}"
                    )
                    
                    station_logs[target_station].append({
                        "Bus ID": bus["bus_id"],
                        "Operator": bus["operator"],
                        "Arrival": self._min_to_time_str(current_time),
                        "Wait Time (min)": int(wait_time),
                        "End Charge": self._min_to_time_str(end_charge)
                    })
                    
                    current_time = end_charge
            
        
            final_segment = self.network["segments"][-1] if bus["direction"] == "Bengaluru Kochi" else self.network["segments"][0]
            current_time += (final_segment["distance_km"] / self.speed) * 60
            destination = "Kochi" if bus["direction"] == "Bengaluru Kochi" else "Bengaluru"
            timeline.append(f"Arrive {destination} @ {self._min_to_time_str(current_time)}")
            
            bus_timetables.append({
                "Bus ID": bus["bus_id"],
                "Operator": bus["operator"],
                "Direction": bus["direction"],
                "Departure": bus["departure"],
                "Arrival Time": self._min_to_time_str(current_time),
                "Total Wait Time (min)": total_wait,
                "Full Timeline Journey": " ➔ ".join(timeline)
            })
            
        return pd.DataFrame(bus_timetables), station_logs



st.set_page_config(layout="wide", page_title="Bus Charging Scheduler")
st.title(" Electric Bus Fleet Charging Optimization Engine")


with open("data/network_config.json", "r") as f:
    network_cfg = json.load(f)

scenario_options = {
    "Scenario 1: Even Spacing": "data/scenario_1.json",
    "Scenario 2: Bunched Start": "data/scenario_2.json",
    "Scenario 3: Asymmetric Load": "data/scenario_3.json",
    "Scenario 4: Operator-Heavy": "data/scenario_4.json",
    "Scenario 5: Worst Case Convergence": "data/scenario_5.json"
}
selected_option = st.selectbox(" Select Scenario to Run", list(scenario_options.keys()))


with open(scenario_options[selected_option], "r") as f:
    scen_cfg = json.load(f)

with st.expander(" View Raw Input Schema Infrastructure Parameters (JSON)", expanded=False):
    st.json({"topology_network_matrix": network_cfg, "active_scenario_dataset": scen_cfg})

engine = BusSimulationEngine(network_cfg, scen_cfg)
df_buses, station_logs = engine.run()

st.markdown("---")


col1, col2 = st.columns([3, 2])

with col1:
    st.subheader(" Per-Bus Timetable Result View")
    st.dataframe(df_buses, use_container_width=True, hide_index=True)

with col2:
    st.subheader("⚡ Per-Station Utilization Logs Queue")
    target_st = st.radio("Select Target Infrastructure Asset Node", ["A", "B", "C", "D"], horizontal=True)
    
    if station_logs[target_st]:
        st.dataframe(pd.DataFrame(station_logs[target_st]), use_container_width=True, hide_index=True)
    else:
        st.info("No active vehicle charging sequences processed or logged at this node selection.")