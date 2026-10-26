"""Tool functions exposed to the ADK agents. Every tool returns a dict with a `status` key."""

from .actions import decide_action, list_actions, propose_action
from .analytics import describe_data_model, run_readonly_sql
from .dock import (assess_inbound_impact, get_dock_exceptions, get_dock_schedule, get_door_utilization,
                                        predict_dock_arrivals, recommend_door)
from .fulfillment import (diagnose_zone_backlog, get_order_fulfillment_summary, get_short_picks, get_wave_progress,
                                               lookup_order, recommend_wave_release)
from .integration import (compare_dc_kpis, get_integration_health, get_wms_landscape,
                                               lookup_field_mapping)
from .inventory import (detect_inventory_anomalies, get_cycle_count_variances, get_expiring_inventory,
                                             get_inventory_position, get_replenishment_needs, get_stockout_risk)
from .labor import forecast_labor_requirement, get_labor_productivity, get_shift_roster
from .slotting import analyze_slotting, get_sku_affinity, get_slot_utilization

INVENTORY_TOOLS = [get_inventory_position, get_expiring_inventory, get_replenishment_needs, get_stockout_risk,
                   get_cycle_count_variances, detect_inventory_anomalies]
SLOTTING_TOOLS = [analyze_slotting, get_sku_affinity, get_slot_utilization]
FULFILLMENT_TOOLS = [get_order_fulfillment_summary, get_wave_progress, diagnose_zone_backlog, get_short_picks,
                     recommend_wave_release, lookup_order]
LABOR_TOOLS = [get_labor_productivity, forecast_labor_requirement, get_shift_roster]
DOCK_TOOLS = [get_dock_schedule, get_dock_exceptions, predict_dock_arrivals, assess_inbound_impact, recommend_door,
              get_door_utilization]
INTEGRATION_TOOLS = [get_wms_landscape, get_integration_health, lookup_field_mapping, compare_dc_kpis]
ANALYTICS_TOOLS = [describe_data_model, run_readonly_sql]
ACTION_TOOLS = [propose_action, decide_action, list_actions]

ALL_TOOLS = (INVENTORY_TOOLS + SLOTTING_TOOLS + FULFILLMENT_TOOLS + LABOR_TOOLS + DOCK_TOOLS + INTEGRATION_TOOLS
             + ANALYTICS_TOOLS + ACTION_TOOLS)
