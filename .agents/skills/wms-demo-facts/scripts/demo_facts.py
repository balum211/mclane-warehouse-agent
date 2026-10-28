"""Print the facts behind each demo beat, straight from the tools (no LLM)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from warehouse_agent import tools as T  # noqa: E402

dc = (sys.argv[1] if len(sys.argv) > 1 else "MTX").upper()

f = T.forecast_labor_requirement(dc)
print(f"[Labor] {dc} tomorrow: required {f['required_hours']} h, available {f['available_hours']} h, "
      f"gap {f['gap_hours']} h ({f['verdict']}), call-outs {len(f['callouts'])}")
for z in f["by_zone"]:
    print(f"   {z['zone']:<8} required {z['required_hours']:>5} h  available {z['available_hours']:>5} h")
for c in f["gap_closing_candidates"][:3]:
    print(f"   candidate: {c['name']} ({c['option']}, OT ${c['ot_cost_per_hour']}/h)")

imp = T.assess_inbound_impact(dc)["trailers"]
if imp:
    t = imp[0]
    print(f"[Inbound] {t['appointment_id']} {t['carrier']} {t['status']}, {t['minutes_late']} min late, "
          f"waiting {t['minutes_waiting']} min: {t['cases_at_risk']} cases at risk on {t['orders_affected']} order lines")
    for c in t["critical_skus"]:
        print(f"   {c['sku']} {c['description']}: {c['cases_at_risk']} cases short without this trailer")
    doors = T.recommend_door(dc, t["appointment_id"])["candidate_doors"]
    print(f"   free doors: {[d['door_id'] for d in doors[:3]]}")

x = T.get_dock_exceptions(dc)
print(f"[Dock] {x['summary']}")
for w in x["waiting_for_door"]:
    print(f"   waiting: {w['appointment_id']} {w['temp_zone']} {w['minutes_waiting']} min (detention risk {w['detention_risk']})")
for m in x["temp_mismatches"]:
    print(f"   temp mismatch: {m['appointment_id']} at {m['door_id']}")

w = T.recommend_wave_release(dc)
print(f"[Waves] crew {w['pickers_available']}, required {w['total_required_picker_hours']} picker-h")
for s in w["sequence"]:
    print(f"   {s['sequence']}. {s['wave_id']} cutoff {s['cutoff_at']} needs {s['required_picker_hours']} h, "
          f"min crew {s['min_pickers_needed']}, feasible {s['feasible_with_crew']}")

s = T.analyze_slotting(dc)
print(f"[Slotting] efficiency {[(z['zone'], z['slotting_efficiency_pct']) for z in s['zones']]}, "
      f"top swaps save {s['total_weekly_hours_saved_top_swaps']} labor h/week")

a = T.detect_inventory_anomalies(dc)
print(f"[Inventory integrity] {a['anomaly_counts']}")
e = T.get_expiring_inventory(dc, 2)
print(f"[FEFO] {e['lot_count']} lots expired/expiring within 2 days, ${e['total_value_usd']:,.0f}")

g = T.get_integration_health(hours=48)
top = g["top_errors"][0] if g["top_errors"] else {}
print(f"[Integration] error rate {g['error_rate_pct']}%, top {top.get('source_system')} {top.get('error_code')} "
      f"x{top.get('count')} at {top.get('dcs')}")

# --- Delivery side: OTD, dwell, geofences, PC*MILER ---
o = T.get_otd_performance()
print(f"[OTD all DCs] this week {o['overall_current']['otd_pct']}% vs prior {o['overall_prior_otd_pct']}%: "
      + ", ".join(f"{k} {v['otd_pct']}%" for k, v in o["by_segment"].items()))
fdl = T.get_otd_performance("FDL")
print(f"[OTD FDL restaurant] {fdl['overall_current']['otd_pct']}% vs {fdl['overall_prior_otd_pct']}% prior, "
      f"late reasons {fdl['overall_current']['late_reasons']}")
rt = T.get_otd_performance(dc, group_by="route")["groups"][0]
print(f"[OTD {dc} worst route] {rt['route']} {rt['current']['otd_pct']}% ({rt['current']['late_reasons']})")
risk = T.assess_route_otd_risk(dc)
fixed = T.assess_route_otd_risk(dc, pickers_available=5)
print(f"[OTD risk tomorrow] crew {risk['pickers_on_waves']}: {risk['total_stops_at_risk']} stops miss windows "
      f"{risk['by_segment']}; with 5 pickers: {fixed['total_stops_at_risk']}")
for r in risk["routes_departing_late"][:4]:
    print(f"   {r['route_id']} ({r['wave_id']}) departs ~{r['projected_departure_delay_min']} min late, "
          f"{r['stops_at_risk']}/{r['stops']} stops at risk")
d = T.get_dwell_time_changes()
if d["inbound_yard"]:
    y = d["inbound_yard"][0]
    print(f"[Dwell inbound] {y['dc_id']} {y['carrier']} {y['avg_dwell_min_prior']} -> {y['avg_dwell_min_current']} min "
          f"(+{y['change_min']}), driver {y['biggest_driver']} {y['component_change_min']}")
if d["customer_stops"]:
    c = d["customer_stops"][0]
    print(f"[Dwell customer] {c['dc_id']} {c['chain']} {c['avg_dwell_min_prior']} -> {c['avg_dwell_min_current']} min "
          f"(std {c['standard_dwell_min']}), OTD {c['otd_pct_current']}%")
gf = T.get_geofence_activity(dc)
print(f"[Geofence] {gf['trailers_in_yard']} trailers in the {dc} yard, {len(gf['trucks_at_customers'])} trucks at customers")
for f in gf["exceptions"]:
    print(f"   {f['flag']}: {f['asset_id']} {f['carrier']} {f['appointment_id']} {f['minutes_in_yard']} min in yard")
lane = T.get_route_miles(dc, route_id=f"{dc}-R07")
print(f"[PC*MILER] {dc}-R07 tomorrow {lane.get('total_practical_miles')} practical miles, "
      f"{lane.get('total_drive_hours')} drive h, source {lane.get('source')}")
