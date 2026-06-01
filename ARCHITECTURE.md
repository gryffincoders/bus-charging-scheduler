## 1. Algorithmic Framework Choice & Rationale
For this system, we rejected a rigid, nested imperative `if/else` loop approach because it creates tight coupling and breaks when business rules change. Instead, this system implements a Discrete Event Simulation (DES) pattern paired with a Pluggable Cost Optimization Scoring Engine.

The main simulation loop acts as a chronological clock, moving vehicles across segments based on constant velocity tracking. When resource contention occurs at a charging station node, the engine delegates the scheduling decision to a collection of independent CostRule classes. This model decouples physical movement from business constraints, ensuring high performance and limitless extensibility.

---

## 2. Data Structure Layout Decisions
To meet the requirement that a "scenario IS your data structure," the system entirely decouples network topology from individual scenario state parameters:

network_config.json: Acts as the immutable physical canvas of the world. It models the sequence of ordered_stations, individual segment lengths, station resource counts (chargers), and global physical constants like vehicle speed and maximum range.
scenario_[1-5].json: Act as operational state snapshots. They contain strictly transient runtime data: individual bus departure tables, operator metadata, and the floating-point priority optimization weights used to evaluate the schedule.

The scheduler reads these structures dynamically, outputting an expressive timeline for each vehicle and a synchronized sequence log for each infrastructure node.

---

 3. Future Changes Anticipated (Zero-Code Modifications)
A core objective of this design is to ensure that modifications to the operational landscape can be implemented through data adjustments alone, with zero changes to the underlying engine:

1. Altering Segment Distances or Adding New Nodes:** If segment distances change or an intermediate station is added (e.g., a "Station E" between C and D), the change is handled by adding the station to the ordered_stations array and updating the segments list inside network_config.json. The travel loop automatically calculates the correct travel offsets.
2.  Upgrading Station Charger Capacity: If a station expands from 1 charger to multiple chargers, changing the chargers integer inside network_config.json handles the upgrade. The engine initializes its internal `station_registry  tracking channels dynamically via list comprehension ([0] * chargers), scaling up capacity automatically.
3.  Introducing Multi-Route Sharing: If entirely different routes start sharing the same hardware stations, those routes can map their paths to the same station keys in the JSON config. Since our engine tracks queue entry states by absolute timestamp, it will safely resolve cross-route resource bottlenecks without issues.

---
4. How to Change a Weight (With Code Example)
Optimization weights are completely externalized within each individual scenario JSON file. To tune how the engine evaluates queues operational priorities, modify the weights key in the active scenario file:

json
"weights": {
  "individual": 1.0,
  "operator": 3.5, 
  "overall": 1.0
}