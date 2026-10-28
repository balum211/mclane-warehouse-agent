"""PC*MILER mileage and geolocation helpers for McLane lanes.

McLane plans and pays routes on PC*MILER (Trimble Maps) practical miles. Lookups resolve in
this order, and every answer says which source it came from:

  1. PC*MILER Web Services, when PCMILER_API_KEY is set (live call, practical or shortest).
  2. The `lane_miles` table: PC*MILER output loaded with the data (synthetic in the demo,
     source = PCMILER_SYNTH; a nightly PC*MILER batch export in production).
  3. A great-circle estimate times a road circuity factor (source = ESTIMATE).

The Web Services request shape follows the PC*MILER REST "routeReports" API. Endpoint, report
names and response fields differ by account and version; set PCMILER_BASE_URL and verify the
parsing below against your Trimble Maps contract before relying on live calls.
"""

from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.request
import zlib

EARTH_RADIUS_MI = 3958.8
DEFAULT_BASE_URL = "https://pcmiler.alk.com/apis/rest/v1.0/Service.svc"


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in statute miles."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))


def destination_point(lat: float, lon: float, bearing_deg: float, miles: float) -> tuple[float, float]:
    """Point `miles` away from (lat, lon) on a compass bearing (0 = north, 90 = east)."""
    d = miles / EARTH_RADIUS_MI
    b = math.radians(bearing_deg)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return round(math.degrees(p2), 6), round(math.degrees(l2), 6)


def circuity(origin_id: str, dest_id: str) -> float:
    """Deterministic road / straight-line ratio for a lane (1.17-1.30, typical for US highway freight)."""
    h = zlib.crc32(f"{min(origin_id, dest_id)}|{max(origin_id, dest_id)}".encode()) % 1000
    return 1.17 + 0.13 * h / 1000


def estimate_drive_minutes(miles: float) -> int:
    """Truck drive time: the first 10 miles at town speed (27 mph), the rest at highway speed (47 mph)."""
    first = min(miles, 10.0)
    return int(round(first / 27 * 60 + (miles - first) / 47 * 60))


def estimate_lane(origin_id: str, o_lat: float, o_lon: float, dest_id: str, d_lat: float, d_lon: float) -> dict:
    """PC*MILER-style lane estimate: practical / shortest miles and drive minutes."""
    practical = haversine_miles(o_lat, o_lon, d_lat, d_lon) * circuity(origin_id, dest_id)
    return {"practical_miles": round(practical, 1), "shortest_miles": round(practical * 0.94, 1),
            "drive_minutes": estimate_drive_minutes(practical)}


def _hours(v) -> float | None:
    """PC*MILER reports hours either as a number or as 'H:MM'."""
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if ":" in str(v):
        h, m = str(v).split(":")[:2]
        return int(h) + int(m) / 60
    return float(v)


def pcmiler_route(stops: list[tuple[float, float]], routing: str | None = None, timeout: float = 8.0) -> dict | None:
    """Call PC*MILER Web Services for a multi-stop route. Returns None when no API key is configured.

    Args:
        stops: [(lat, lon), ...] in visit order (at least two).
        routing: "Practical" (default, PCMILER_ROUTING) or "Shortest".
    """
    key = os.environ.get("PCMILER_API_KEY")
    if not key or len(stops) < 2:
        return None
    routing = routing or os.environ.get("PCMILER_ROUTING", "Practical")
    base = os.environ.get("PCMILER_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    query = urllib.parse.urlencode({
        "stops": ";".join(f"{lon},{lat}" for lat, lon in stops),
        "reports": "Mileage",
        "routeOpt": routing,
        "vehType": os.environ.get("PCMILER_VEHICLE_TYPE", "0"),  # 0 = truck
    }, safe=";,")
    req = urllib.request.Request(f"{base}/route/routeReports?{query}",
                                 headers={"Authorization": key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https endpoint)
        data = json.loads(resp.read().decode())
    reports = data if isinstance(data, list) else [data]
    for rep in reports:
        lines = rep.get("ReportLines") or []
        total = lines[-1] if lines else rep
        miles = total.get("TMiles") or total.get("TotalMiles")
        if miles is not None:
            hours = _hours(total.get("THours") or total.get("TotalHours"))
            return {"practical_miles" if routing.lower() == "practical" else "shortest_miles": round(float(miles), 1),
                    "drive_minutes": int(round(hours * 60)) if hours is not None else None,
                    "source": "PCMILER_API", "routing": routing}
    raise ValueError("PC*MILER response had no TMiles; check PCMILER_BASE_URL and the report type.")
