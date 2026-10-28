# Tasks: McLane delivery view

- [x] T001 Add delivery tables and columns to `warehouse_agent/schema.py`; re-render `sql/` and `docs/DATA_MODEL.md`
- [x] T002 `warehouse_agent/pcmiler.py` geo helpers, estimate and PC*MILER Web Services client
- [x] T003 `warehouse_data/delivery.py`: geolocations, geofences, windows, lanes, trips, stops, events, yard history
- [x] T004 Plant FDL late departures, MTX-R07 traffic, Taco Trail dwell, Lonestar yard dwell, early trailer in yard
- [x] T005 Verify warehouse demo facts unchanged (`demo_facts.py MTX` diff)
- [x] T006 `tools/delivery.py` seven tools; register `DELIVERY_TOOLS`
- [x] T007 `delivery_otd_agent`, briefing collector, re-plan assessor, prompts
- [x] T008 New action types RESEQUENCE_ROUTE, NOTIFY_CUSTOMER with approver
- [x] T009 Tests: `tests/test_delivery.py`, portability CALLS, agent flow
- [x] T010 Docs: architecture 2.5, demo beat 6, Antigravity prompts, skill `mclane-otd-dwell`
- [ ] T011 Replace `PCMILER_SYNTH` lanes with a PC*MILER batch export for real McLane lanes (pilot)
- [ ] T012 Stream telematics geofence events through Pub/Sub (pilot)
