# Research notes

- **Velocity-based slotting**: put the highest pick-frequency SKUs in the faces with the shortest
  travel (golden zone, near the dock); efficiency metric = ideal travel / current travel, where
  ideal assigns the k-th fastest SKU to the k-th closest face within a temperature zone.
- **Affinity**: lift = P(A and B) / (P(A) P(B)) over orders; co-locate high-lift pairs that sit far apart.
- **Ergonomics**: heavy cases (35 lb or more) with high velocity belong at floor level.
- **Engineered labor standards**: performance % = earned hours (units / standard rate) / direct
  hours; 85% utilization of scheduled hours as direct time.
- **Wave planning**: earliest-deadline-first by trailer cutoff (departure minus load time).
- **Dock**: detention typically starts after 2 hours of waiting; cold-chain loads need
  refrigerated doors; baseline arrival prediction = carrier median lateness (replace with a Vertex AI
  forecasting model in the pilot).
- **Inventory integrity**: anomaly rules (negative on-hand, over-allocation, expired-but-available,
  over-capacity, temp-zone mismatch, stale holds) drive a risk-ranked cycle count list.
- **ADK**: InstructionProvider callables read session state set by `output_key` in parallel
  collectors; transfers via `transfer_to_agent`.
