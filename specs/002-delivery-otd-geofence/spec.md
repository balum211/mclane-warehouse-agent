# Feature Specification: McLane delivery view (PC*MILER, geofences, dwell, Retail and Restaurant OTD)

**Feature Branch**: `002-delivery-otd-geofence`
**Created**: 2026-10-28
**Status**: Implemented
**Input**: "McLane uses PC*MILER, Dwell Time Change, Retail & Restaurant On-time Delivery (OTD),
Geofence, Geo locations." Connect what happens in the DC to whether stores and restaurants get
their delivery inside the receiving window.

## User Scenarios & Testing

### User Story 1: Why is OTD down? (Priority: P1)
A transportation manager asks "Why is restaurant OTD down at FDL?" and gets this week vs last week,
Retail and Restaurant separately, and the main late reason, with one next action.

**Acceptance Scenarios**:
1. **Given** delivered stops with receiving windows, **Then** OTD % is reported by segment (and by
   DC, route, chain or customer on request) for the current and prior period with the change in points.
2. **Given** late stops, **Then** each is attributed to LATE_DEPARTURE, CUSTOMER_DWELL, TRAFFIC or
   ROUTE_PLAN and the answer leads with the biggest reason.

### User Story 2: Dwell time changes (Priority: P1)
"Is dwell going up anywhere?" finds carriers whose DC yard dwell rose (gate-to-door, unload,
door-to-gate) and chains whose stop dwell rose against standard.

### User Story 3: Geofence activity (Priority: P2)
"Which trucks are in the yard?" lists trailers inside the DC yard geofence with minutes on site,
flags IN_YARD_NOT_CHECKED_IN and DETENTION_RISK, and shows McLane trucks at customers now.

### User Story 4: Disruption re-plan includes customer impact (Priority: P1)
The mid-shift re-plan shows which routes leave late from tonight's waves and how many Retail and
Restaurant stops miss their window, before and after the re-plan.

### User Story 5: PC*MILER miles and customer geolocation (Priority: P2)
"How many PC*MILER miles is route FDL-R03?" and "Where is Taco Trail #2084 and when do they take
deliveries?" return practical miles, drive time, the miles source, geofence and window.

## Requirements
- **FR-001**: Geolocate every DC and customer; one circular geofence per site (yard 450 m, retail
  120 m, restaurant 90 m).
- **FR-002**: Receiving windows: restaurant 60 min, retail 120 min; standard dwell per customer.
- **FR-003**: Route trips and stops for 14 days of history, today (in transit at 10:30) and
  tomorrow (planned), linked to `outbound_orders`.
- **FR-004**: Telematics ENTER / EXIT events for yard and customer geofences, none after the clock.
- **FR-005**: PC*MILER lanes (practical, shortest, drive minutes) for every lane used; live API when
  `PCMILER_API_KEY` is set, else table, else labelled estimate.
- **FR-006**: Tools are read-only, portable SQL, return `status`; changes go through
  `propose_action` (new types RESEQUENCE_ROUTE, NOTIFY_CUSTOMER, approver transportation manager).
- **FR-007**: Adding the delivery data must not change any warehouse demo number.

## Success Criteria
- **SC-001**: `tests/test_delivery.py` passes for every planted scenario; DuckDB portability passes for
  every new tool.
- **SC-002**: `demo_facts.py MTX` warehouse numbers identical before and after the feature.
- **SC-003**: Shift briefing and re-plan include delivery facts in the scripted end-to-end test.
