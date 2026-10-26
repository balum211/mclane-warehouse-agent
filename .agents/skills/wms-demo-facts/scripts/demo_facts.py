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
