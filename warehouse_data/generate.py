"""Synthetic WMS data generator for McLane-style retail and restaurant distribution.

Produces one CSV per table in `warehouse_data/schema.py`. The data is
deterministic (seeded) and anchored to an "as of" date so demos are
reproducible. The demo clock is 10:30 local on the anchor date ("today"):
orders that shipped on or before today are history (14 days), and orders
shipping tomorrow are released and being picked today and tonight.

Planted operational problems the agents should find:
  * fast movers slotted far from the dock, slow movers in golden-zone slots
  * pick faces below min with reserve stock available (replenishment)
  * cooler/freezer lots expiring in the next few days
  * a late inbound carrier, a long-waiting checked-in trailer, a double-booked
    door, and a freezer load assigned to a non-refrigerated door
  * call-outs that leave tomorrow's night shift short of required pick hours
  * an integration error spike (UOM mismatch) on one Blue Yonder DC
  * cycle count variances concentrated on a few high-value SKUs

All names are fictional. Source-system message names are illustrative.

Usage:
    python -m warehouse_data.generate --out data/ --as-of 2026-10-27 --scale 1.0
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

from warehouse_data.schema import TABLES, columns

DEFAULT_AS_OF = date(2026, 10, 27)

DCS = [
    # dc_id, name, city, state, segment, wms_system, sqft, tz
    ("MTX", "Central Texas Grocery DC", "Temple", "TX", "RETAIL", "MANHATTAN_ACTIVE", 410_000, "America/Chicago"),
    ("MGA", "Southeast Grocery DC", "Forest Park", "GA", "RETAIL", "MANHATTAN_ACTIVE", 380_000, "America/New_York"),
    ("MCA", "Inland Empire Grocery DC", "Ontario", "CA", "RETAIL", "BLUE_YONDER", 450_000, "America/Los_Angeles"),
    ("MNY", "Northeast Grocery DC", "Baldwinsville", "NY", "RETAIL", "BLUE_YONDER", 360_000, "America/New_York"),
    ("FDL", "North Texas Foodservice DC", "Carrollton", "TX", "RESTAURANT", "ARGENT", 260_000, "America/Chicago"),
    ("FOH", "Ohio Valley Foodservice DC", "Columbus", "OH", "RESTAURANT", "ARGENT", 240_000, "America/New_York"),
]

RETAIL_CATALOG = {
    # category: (temp_zone, share, cost range per case, shelf life days, sample nouns)
    "Candy & Gum": ("DRY", 0.16, (18, 65), 270, ["Chocolate Bar", "Peanut Cups", "Gummy Bears", "Mint Gum", "Sour Strips", "Caramel Chews"]),
    "Salty Snacks": ("DRY", 0.14, (14, 40), 120, ["Potato Chips", "Tortilla Chips", "Pretzels", "Cheese Puffs", "Pork Rinds", "Trail Mix"]),
    "Beverages": ("DRY", 0.14, (9, 32), 270, ["Cola 20oz", "Lemon-Lime 20oz", "Energy Drink 16oz", "Sports Drink 28oz", "Spring Water 16.9oz", "Iced Tea 18.5oz"]),
    "Grocery": ("DRY", 0.10, (12, 45), 365, ["Canned Chili", "Instant Noodles", "Peanut Butter", "Bread Loaf", "Cereal Cup", "Beef Jerky"]),
    "Health & Beauty": ("DRY", 0.08, (20, 90), 0, ["Pain Reliever 2ct", "Antacid Roll", "Lip Balm", "Allergy Tabs", "Hand Sanitizer", "Bandages"]),
    "General Merchandise": ("DRY", 0.08, (15, 80), 0, ["Lighter", "Phone Cable", "Batteries AA", "Sunglasses", "Air Freshener", "Motor Oil Qt"]),
    "Automotive & Fuel Additives": ("DRY", 0.04, (25, 70), 0, ["Fuel Injector Cleaner", "Windshield Fluid", "Octane Boost", "Tire Gauge"]),
    "Dairy & Deli": ("COOLER", 0.10, (16, 55), 21, ["Whole Milk Qt", "Yogurt Cup", "Cheese Stick", "Deli Sandwich", "Creamer Pint", "Egg Bites"]),
    "Frozen": ("FREEZER", 0.10, (20, 70), 180, ["Ice Cream Bar", "Frozen Burrito", "Ice 10lb", "Frozen Pizza Slice", "Ice Pop", "Breakfast Sandwich"]),
    "Bakery Sweets": ("DRY", 0.06, (12, 36), 30, ["Honey Bun", "Snack Cake", "Donut Sticks", "Cookie Pack", "Fruit Pie"]),
}

RESTAURANT_CATALOG = {
    "Proteins - Frozen": ("FREEZER", 0.20, (55, 160), 270, ["Beef Patty 4oz", "Chicken Breast Fillet", "Breaded Tenders", "Fish Portion", "Sausage Patty", "Chicken Wings"]),
    "Fries & Sides - Frozen": ("FREEZER", 0.10, (28, 60), 365, ["Shoestring Fries", "Hash Brown Patty", "Onion Rings", "Tater Bites", "Mozzarella Sticks"]),
    "Produce": ("COOLER", 0.12, (18, 55), 10, ["Shredded Lettuce", "Tomato 5x6", "Diced Onion", "Pickle Chips", "Sliced Jalapeno", "Avocado Pulp"]),
    "Dairy": ("COOLER", 0.10, (25, 75), 45, ["American Cheese Slice", "Shredded Cheddar", "Sour Cream Cup", "Soft Serve Mix", "Liquid Eggs"]),
    "Bakery": ("DRY", 0.10, (16, 40), 14, ["Sesame Bun 4in", "Brioche Bun", "Flour Tortilla 12in", "Biscuit Dough", "Hoagie Roll"]),
    "Sauces & Dry Grocery": ("DRY", 0.12, (20, 65), 365, ["Ketchup Packet", "Mayo Pouch", "BBQ Sauce Cup", "Fry Oil 35lb", "Breading Mix", "Seasoning Salt"]),
    "Paper & Packaging": ("DRY", 0.16, (22, 90), 0, ["Cup 32oz", "Lid 32oz", "Clamshell Box", "Napkin Pack", "Fry Carton", "Straw Wrapped"]),
    "Janitorial": ("DRY", 0.05, (30, 110), 0, ["Sanitizer Concentrate", "Degreaser", "Nitrile Gloves", "Trash Liner 55gal"]),
    "Beverage Syrup": ("DRY", 0.05, (60, 140), 180, ["Cola Syrup BIB", "Lemonade Syrup BIB", "Sweet Tea Concentrate", "Coffee Pouch"]),
}

BOTH_CATALOG = {
    "Coffee & Hot Beverage": ("DRY", 0.40, (30, 95), 300, ["Coffee Ground 2.5oz", "Creamer Cup", "Hot Cup 16oz", "Sugar Packet"]),
    "Foodservice Disposables": ("DRY", 0.60, (18, 70), 0, ["Food Tray", "Foil Wrap Sheet", "Deli Paper", "Portion Cup 2oz", "Utensil Kit"]),
}

BRANDS = ["Lone Star", "Summit", "Harvest Hill", "BlueRidge", "Prairie Gold", "Sunbelt", "Cascade", "Red River",
          "Golden Fork", "Liberty", "Northstar", "Pecos", "Magnolia", "Ironwood", "Brazos"]
SUPPLIERS = ["Heartland Foods Co", "Gulf Coast Beverage", "Sweetwater Confections", "Prairie Protein Packers",
             "Valley Fresh Produce", "Summit Paper Products", "Great Plains Grocery", "Lakeside Dairy Coop",
             "Ironwood Packaging", "Sunbelt Snacks", "Northstar Frozen", "Delta Janitorial Supply"]
RETAIL_CHAINS = ["QuickStop", "Lone Star Fuel & Go", "Pump N Munch", "Corner Market", "Road Ranger Express",
                 "Sunrise Mart", "Big Sky Travel Center", "Kwik Corner"]
RESTAURANT_CHAINS = ["Burger Barn", "Taco Trail", "Coop Chicken Express", "Sub Station Deli", "Biscuit Brothers",
                     "Pizza Pronto", "Wing Ranch", "Sonic Sky Drive-In"]
CARRIERS = ["Swift Haul", "Prairie Freight", "Lonestar Logistics", "Coldline Reefer", "Atlas Dedicated",
            "Bluebonnet Carriers", "Northline Transport", "McLane Fleet"]
FIRST = ["Maria", "James", "Luis", "Ashley", "DeShawn", "Priya", "Tyler", "Carmen", "Kevin", "Grace", "Andre", "Linh",
         "Jose", "Megan", "Omar", "Brianna", "Derek", "Sofia", "Marcus", "Hannah", "Victor", "Keisha", "Ryan", "Elena"]
LAST = ["Garcia", "Johnson", "Nguyen", "Smith", "Patel", "Williams", "Hernandez", "Brown", "Lopez", "Davis",
        "Martinez", "Wilson", "Anderson", "Thomas", "Moore", "Jackson", "Lee", "Walker", "Young", "King"]

# Illustrative source-native message names per canonical interface.
SOURCE_MESSAGES = {
    "MANHATTAN_ACTIVE": {"ITEM_MASTER": "ItemSync", "ASN": "AsnInbound", "ORDER_RELEASE": "OriginalOrderImport",
                         "SHIP_CONFIRM": "OlpnShipConfirm", "INVENTORY_SYNC": "InventorySnapshot",
                         "RECEIPT_CONFIRM": "ReceiptVerification"},
    "BLUE_YONDER": {"ITEM_MASTER": "PART_INB_IFD", "ASN": "INB_SHIPMENT_IFD", "ORDER_RELEASE": "ORDER_INB_IFD",
                    "SHIP_CONFIRM": "SHIP_LOAD_OUB_IFD", "INVENTORY_SYNC": "INV_SNAPSHOT_OUB_IFD",
                    "RECEIPT_CONFIRM": "RCPT_CLOSE_OUB_IFD"},
    "ARGENT": {"ITEM_MASTER": "ItemMaintenance", "ASN": "InboundASN", "ORDER_RELEASE": "OrderDownload",
               "SHIP_CONFIRM": "ShipmentUpload", "INVENTORY_SYNC": "InventoryReconcile",
               "RECEIPT_CONFIRM": "ReceiptUpload"},
}

FIELD_MAP = [
    # source_system, source_entity, source_field, canonical_table, canonical_field, transform
    ("MANHATTAN_ACTIVE", "Item", "ItemId", "items", "sku", "trim; uppercase"),
    ("MANHATTAN_ACTIVE", "Item", "Description", "items", "description", "none"),
    ("MANHATTAN_ACTIVE", "Item", "ProtectionLevelId", "items", "temp_zone", "map AMBIENT->DRY, CHILLED->COOLER, FROZEN->FREEZER"),
    ("MANHATTAN_ACTIVE", "Location", "LocationId", "locations", "location_id", "prefix with dc_id"),
    ("MANHATTAN_ACTIVE", "Inventory", "OnHand", "inventory", "qty_on_hand", "convert eaches to cases using case_pack"),
    ("MANHATTAN_ACTIVE", "Inventory", "BatchNumber", "inventory", "lot_number", "none"),
    ("MANHATTAN_ACTIVE", "Inventory", "ExpirationDate", "inventory", "expiry_date", "ISO-8601 date"),
    ("MANHATTAN_ACTIVE", "OriginalOrder", "OrderId", "outbound_orders", "order_id", "none"),
    ("MANHATTAN_ACTIVE", "Wave", "WaveRunId", "waves", "wave_id", "none"),
    ("MANHATTAN_ACTIVE", "Task", "TaskId", "pick_tasks", "task_id", "none"),
    ("MANHATTAN_ACTIVE", "Appointment", "AppointmentId", "dock_appointments", "appointment_id", "none"),
    ("BLUE_YONDER", "PART", "PRTNUM", "items", "sku", "strip client prefix"),
    ("BLUE_YONDER", "PART", "LNGDSC", "items", "description", "none"),
    ("BLUE_YONDER", "PART", "TEMP_ZONE_CD", "items", "temp_zone", "map A->DRY, R->COOLER, F->FREEZER"),
    ("BLUE_YONDER", "LOCMST", "STOLOC", "locations", "location_id", "prefix with dc_id"),
    ("BLUE_YONDER", "INVDTL", "UNTQTY", "inventory", "qty_on_hand", "divide by UNTCAS"),
    ("BLUE_YONDER", "INVDTL", "LOTNUM", "inventory", "lot_number", "none"),
    ("BLUE_YONDER", "INVDTL", "EXPIRE_DTE", "inventory", "expiry_date", "YYYYMMDD -> DATE"),
    ("BLUE_YONDER", "ORD", "ORDNUM", "outbound_orders", "order_id", "none"),
    ("BLUE_YONDER", "PCKWRK", "WRKREF", "pick_tasks", "task_id", "none"),
    ("BLUE_YONDER", "PCKWRK", "SCHBAT", "waves", "wave_id", "none"),
    ("BLUE_YONDER", "APPT", "APPT_ID", "dock_appointments", "appointment_id", "none"),
    ("ARGENT", "Item", "ItemNumber", "items", "sku", "left-pad to 6"),
    ("ARGENT", "Item", "ItemDesc", "items", "description", "none"),
    ("ARGENT", "Item", "StorageClass", "items", "temp_zone", "map DRY/CLR/FRZ"),
    ("ARGENT", "Slot", "SlotCode", "locations", "location_id", "prefix with dc_id"),
    ("ARGENT", "Stock", "QtyCases", "inventory", "qty_on_hand", "none"),
    ("ARGENT", "Stock", "CodeDate", "inventory", "expiry_date", "MMDDYY -> DATE"),
    ("ARGENT", "Order", "InvoiceNumber", "outbound_orders", "order_id", "none"),
    ("ARGENT", "Selection", "SelectionId", "pick_tasks", "task_id", "none"),
    ("ARGENT", "DoorSchedule", "DoorApptNo", "dock_appointments", "appointment_id", "none"),
]

LABOR_STANDARDS = [
    ("PICKER", "DRY", 165.0), ("PICKER", "COOLER", 140.0), ("PICKER", "FREEZER", 115.0),
    ("LOADER", "DRY", 420.0), ("LOADER", "COOLER", 380.0), ("LOADER", "FREEZER", 340.0),
    ("RECEIVER", "DRY", 520.0), ("RECEIVER", "COOLER", 470.0), ("RECEIVER", "FREEZER", 430.0),
    ("FORKLIFT", "DRY", 30.0), ("FORKLIFT", "COOLER", 26.0), ("FORKLIFT", "FREEZER", 22.0),
]

ZONE_LAYOUT = {"DRY": (8, 0), "COOLER": (3, 110), "FREEZER": (2, 150)}  # aisles, extra distance from dock (ft)
BAYS, LEVELS = 20, 5


class Gen:
    def __init__(self, as_of: date, scale: float, seed: int):
        self.as_of = as_of
        self.scale = scale
        self.r = random.Random(seed)
        self.now = datetime.combine(as_of, time(10, 30))  # demo "current time"
        self.rows: dict[str, list[dict]] = {t: [] for t in TABLES}
        self._seq: dict[str, int] = {}

    def nid(self, prefix: str, width: int = 7) -> str:
        n = self._seq.get(prefix, 0) + 1
        self._seq[prefix] = n
        return f"{prefix}{n:0{width}d}"

    def add(self, table: str, **row):
        self.rows[table].append(row)

    # ------------------------------------------------------------------ masters
    def build_masters(self):
        r = self.r
        for dc in DCS:
            self.add("distribution_centers", dc_id=dc[0], dc_name=dc[1], city=dc[2], state=dc[3], segment=dc[4],
                     wms_system=dc[5], square_feet=dc[6], timezone=dc[7])
        for role, zone, rate in LABOR_STANDARDS:
            self.add("labor_standards", role=role, zone=zone, engineered_rate=rate)
        for row in FIELD_MAP:
            self.add("wms_field_map", **dict(zip(columns("wms_field_map"), row)))

        self.items: list[dict] = []
        n_retail, n_rest, n_both = int(300 * self.scale), int(150 * self.scale), int(50 * self.scale)
        for segment, catalog, n in (("RETAIL", RETAIL_CATALOG, n_retail), ("RESTAURANT", RESTAURANT_CATALOG, n_rest),
                                    ("BOTH", BOTH_CATALOG, n_both)):
            cats = list(catalog.items())
            for i in range(n):
                cat, (zone, _share, (lo, hi), life, nouns) = r.choices(cats, weights=[c[1][1] for c in cats])[0]
                sku = f"{100000 + len(self.items) + 1}"
                pack = r.choice([6, 8, 12, 24, 36, 48]) if zone == "DRY" else r.choice([4, 6, 10, 12])
                desc = f"{r.choice(BRANDS)} {r.choice(nouns)} {pack}ct"
                item = dict(sku=sku, description=desc, category=cat, segment=segment, temp_zone=zone, uom="CS",
                            case_pack=pack, case_cube_ft=round(r.uniform(0.4, 2.6), 2),
                            case_weight_lb=round(r.uniform(4, 42), 1), unit_cost=round(r.uniform(lo, hi), 2),
                            shelf_life_days=life, supplier=r.choice(SUPPLIERS))
                # Pareto demand: a few SKUs carry most of the volume.
                item["_demand"] = r.paretovariate(1.3)
                self.items.append(item)
                self.add("items", **{k: v for k, v in item.items() if not k.startswith("_")})
        self.item_by_sku = {i["sku"]: i for i in self.items}

        self.dc_items: dict[str, list[dict]] = {}
        for dc in DCS:
            seg = dc[4]
            self.dc_items[dc[0]] = [i for i in self.items if i["segment"] in (seg, "BOTH")]

    def build_network(self):
        r = self.r
        self.routes: dict[str, list[dict]] = {}
        self.customers: dict[str, list[dict]] = {}
        for dc_id, _n, city, state, seg, *_ in DCS:
            n_routes = 12
            routes = []
            for k in range(n_routes):
                # Night-pick operation: trailers leave between 03:00 and 08:30 on ship date.
                dep = time(3 + (k * 5) // 12 + (k % 2), 30 if k % 3 == 0 else 0)
                route = dict(route_id=f"{dc_id}-R{k + 1:02d}", dc_id=dc_id, departure_time=dep.strftime("%H:%M"),
                             stops=0, trailer_type="MULTI_TEMP")
                routes.append(route)
            n_cust = int(180 * self.scale)
            custs = []
            chains = RETAIL_CHAINS if seg == "RETAIL" else RESTAURANT_CHAINS
            for c in range(n_cust):
                route = routes[c % n_routes]
                route["stops"] += 1
                chain = r.choice(chains)
                cust = dict(customer_id=f"C{dc_id}{c + 1:04d}", customer_name=f"{chain} #{r.randint(100, 9999)}",
                            chain=chain, segment=seg, dc_id=dc_id, route_id=route["route_id"],
                            city=city, state=state)
                cust["_days"] = set(r.sample(range(7), k=r.choice([2, 3, 3, 4])))
                custs.append(cust)
                self.add("customers", **{k: v for k, v in cust.items() if not k.startswith("_")})
            for route in routes:
                self.add("routes", **route)
            self.routes[dc_id] = routes
            self.customers[dc_id] = custs

    def build_facility(self):
        """Locations, slotting (deliberately imperfect), inventory, doors, associates."""
        r = self.r
        self.pick_loc: dict[tuple[str, str], dict] = {}
        self.locations: dict[str, dict] = {}
        for dc_id, *_ in DCS:
            pick_by_zone: dict[str, list[dict]] = {"DRY": [], "COOLER": [], "FREEZER": []}
            reserve_by_zone: dict[str, list[dict]] = {"DRY": [], "COOLER": [], "FREEZER": []}
            seq = 0
            for zone, (aisles, offset) in ZONE_LAYOUT.items():
                for a in range(aisles):
                    aisle = f"{zone[0]}{a + 1:02d}"
                    for bay in range(1, BAYS + 1):
                        for level in range(1, LEVELS + 1):
                            seq += 1
                            ltype = "PICK" if level <= 2 else "RESERVE"
                            dist = round(offset + 40 + a * 14 + bay * 9 + (level - 1) * 2, 1)
                            loc = dict(location_id=f"{dc_id}-{aisle}-{bay:02d}-{level}", dc_id=dc_id, zone=zone,
                                       aisle=aisle, bay=bay, level=level, location_type=ltype,
                                       is_golden_zone=int(ltype == "PICK" and bay <= 6 and level == 2 or
                                                          ltype == "PICK" and bay <= 4),
                                       capacity_cases=60 if ltype == "PICK" else 240,
                                       distance_to_dock_ft=dist, pick_sequence=seq)
                            self.add("locations", **loc)
                            self.locations[loc["location_id"]] = loc
                            (pick_by_zone if ltype == "PICK" else reserve_by_zone)[zone].append(loc)

            # Slotting: mostly random (legacy slotting never re-run), so velocity and travel are misaligned.
            items = self.dc_items[dc_id]
            for zone in pick_by_zone:
                zitems = [i for i in items if i["temp_zone"] == zone]
                faces = pick_by_zone[zone][:]
                r.shuffle(faces)
                # Only 10% of SKUs were slotted by velocity (closest faces to the fastest movers); the rest random.
                ranked = sorted(zitems, key=lambda i: -i["_demand"])
                close = sorted(pick_by_zone[zone], key=lambda l: l["distance_to_dock_ft"])
                used = set()
                assignment = {}
                for i in ranked[: int(len(ranked) * 0.1)]:
                    loc = next(l for l in close if l["location_id"] not in used)
                    used.add(loc["location_id"])
                    assignment[i["sku"]] = loc
                rest = [l for l in faces if l["location_id"] not in used]
                for i, loc in zip(ranked[int(len(ranked) * 0.1):], rest):
                    assignment[i["sku"]] = loc
                for sku, loc in assignment.items():
                    mx = int(r.choice([30, 40, 50, 60]))
                    mn = max(4, int(mx * 0.25))
                    self.pick_loc[(dc_id, sku)] = dict(loc=loc, min=mn, max=mx)
                    self.add("slot_assignments", dc_id=dc_id, location_id=loc["location_id"], sku=sku, min_qty=mn,
                             max_qty=mx, assigned_date=(self.as_of - timedelta(days=r.randint(120, 900))).isoformat())

            self.reserve_pool = getattr(self, "reserve_pool", {})
            self.reserve_pool[dc_id] = {z: l[:] for z, l in reserve_by_zone.items()}
            for z in self.reserve_pool[dc_id]:
                r.shuffle(self.reserve_pool[dc_id][z])

            # Dock doors
            self.doors = getattr(self, "doors", {})
            doors = []
            for d in range(1, 13):
                doors.append(dict(door_id=f"{dc_id}-IB{d:02d}", dc_id=dc_id, door_type="INBOUND",
                                  temp_capable=int(d > 6)))
            for d in range(1, 17):
                doors.append(dict(door_id=f"{dc_id}-OB{d:02d}", dc_id=dc_id, door_type="OUTBOUND",
                                  temp_capable=int(d > 4)))
            for dd in doors:
                self.add("dock_doors", **dd)
            self.doors[dc_id] = doors

            # Associates
            self.associates = getattr(self, "associates", {})
            assoc = []
            mix = [("PICKER", 12), ("LOADER", 5), ("RECEIVER", 5), ("FORKLIFT", 4)]
            for role, n in mix:
                for k in range(int(n * max(self.scale, 0.5))):
                    zone = r.choices(["DRY", "COOLER", "FREEZER"], weights=[0.6, 0.2, 0.2])[0]
                    shift = "NIGHT" if role in ("PICKER", "LOADER", "FORKLIFT") and r.random() < 0.7 else "DAY"
                    if role == "RECEIVER":
                        shift = "DAY"
                    a = dict(associate_id=self.nid(f"A{dc_id}", 4), dc_id=dc_id,
                             associate_name=f"{r.choice(FIRST)} {r.choice(LAST)}", role=role, home_zone=zone,
                             shift=shift,
                             hire_date=(self.as_of - timedelta(days=r.randint(20, 3000))).isoformat(),
                             hourly_rate=round(r.uniform(17.5, 26.0), 2))
                    a["_perf"] = max(0.55, min(1.3, r.gauss(0.96, 0.13)))
                    if (self.as_of - date.fromisoformat(a["hire_date"])).days < 60:
                        a["_perf"] *= 0.75  # new hires ramping
                    assoc.append(a)
                    self.add("associates", **{k: v for k, v in a.items() if not k.startswith("_")})
            self.associates[dc_id] = assoc

    def _add_inv(self, dc_id, loc_id, item, qty, life, reserve=False, allocated=0):
        r = self.r
        window = 40 if reserve else 25
        if life:
            window = max(1, min(window, int(life * 0.6)))
        received = self.as_of - timedelta(days=r.randint(1, window))
        expiry = None
        if life:
            expiry = received + timedelta(days=life)
            if item["temp_zone"] != "DRY" and r.random() < 0.08:
                expiry = self.as_of + timedelta(days=r.randint(-1, 5))  # short-dated
        status = r.choices(["AVAILABLE", "HOLD", "DAMAGED", "QC"], weights=[0.93, 0.03, 0.02, 0.02])[0]
        self.add("inventory", inventory_id=self.nid("INV"), dc_id=dc_id, location_id=loc_id, sku=item["sku"],
                 lot_number=f"L{received.strftime('%y%m%d')}{r.randint(10, 99)}", qty_on_hand=qty,
                 qty_allocated=allocated if status == "AVAILABLE" else 0, status=status, received_date=received.isoformat(),
                 expiry_date=expiry.isoformat() if expiry else None)

    # --------------------------------------------------------------- operations
    def build_orders(self):
        r = self.r
        start = self.as_of - timedelta(days=14)
        alloc: dict[tuple[str, str], int] = {}
        self.hist_demand: dict[tuple[str, str], int] = {}
        for dc_id, *_ in DCS:
            items = [i for i in self.dc_items[dc_id] if (dc_id, i["sku"]) in self.pick_loc]
            weights = [i["_demand"] for i in items]
            pickers = [a for a in self.associates[dc_id] if a["role"] == "PICKER"]
            for offset in range(15):  # ship dates as_of-13 .. as_of+1
                order_date = start + timedelta(days=offset)
                ship_date = order_date + timedelta(days=1)
                # Orders shipping tomorrow are released and being picked today/tonight ("inflight").
                day_kind = "past" if ship_date <= self.as_of else "inflight"
                orders_by_route: dict[str, list[tuple[dict, list]]] = {}
                for cust in self.customers[dc_id]:
                    if ship_date.weekday() not in cust["_days"]:
                        continue
                    n_lines = max(3, int(r.gauss(18, 6)))
                    skus = {}
                    for item in r.choices(items, weights=weights, k=n_lines):
                        skus[item["sku"]] = item
                    lines = []
                    for ln, item in enumerate(skus.values(), start=1):
                        qty = max(1, int(r.expovariate(1 / (2 + min(item["_demand"], 8)))))
                        lines.append((ln, item, qty))
                    orders_by_route.setdefault(cust["route_id"], []).append((cust, lines))

                route_dep = {rt["route_id"]: rt["departure_time"] for rt in self.routes[dc_id]}
                # One wave per route group (3 routes each) per ship date.
                route_ids = sorted(orders_by_route)
                for g in range(0, len(route_ids), 3):
                    group = route_ids[g:g + 3]
                    wave_id = self.nid(f"W{dc_id}", 5)
                    earliest = min(route_dep[x] for x in group)
                    dep_dt = datetime.combine(ship_date, time.fromisoformat(earliest))
                    cutoff = dep_dt - timedelta(minutes=90)
                    released = datetime.combine(order_date, time(8, 0)) + timedelta(minutes=45 * (g // 3))
                    n_orders = sum(len(orders_by_route[x]) for x in group)
                    n_lines = sum(len(l) for x in group for _c, l in orders_by_route[x])
                    if day_kind == "past":
                        w_status = "COMPLETE"
                    else:
                        w_status = "IN_PROGRESS" if g < 6 else "RELEASED"
                    self.add("waves", wave_id=wave_id, dc_id=dc_id, ship_date=ship_date.isoformat(), wave_type="ROUTE",
                             temp_zone="MIXED", released_at=_dt(released),
                             cutoff_at=_dt(cutoff), status=w_status, order_count=n_orders, line_count=n_lines)
                    for rid in group:
                        for cust, lines in orders_by_route[rid]:
                            self._emit_order(dc_id, cust, lines, order_date, ship_date, wave_id, w_status, day_kind,
                                             released, pickers, alloc)

        self.open_demand = alloc

    def build_inventory(self):
        """Inventory sized from real demand: a pick face per slotted SKU plus reserve pallets holding
        5-14 days of supply. A few SKUs per DC are planted as true stockouts (no reserve)."""
        r = self.r
        for dc_id, *_ in DCS:
            items = [i for i in self.dc_items[dc_id] if (dc_id, i["sku"]) in self.pick_loc]
            in_demand = [i for i in items if self.open_demand.get((dc_id, i["sku"]), 0) >= 6]
            stockouts = {i["sku"] for i in r.sample(in_demand or items, k=3)}
            self.stockouts = getattr(self, "stockouts", {})
            self.stockouts[dc_id] = sorted(stockouts)
            pool = self.reserve_pool[dc_id]
            spare_dry = pool["DRY"].pop()  # kept free for the planted temp-zone anomaly below
            for item in items:
                key = (dc_id, item["sku"])
                slot = self.pick_loc[key]
                life = item["shelf_life_days"]
                open_qty = self.open_demand.get(key, 0)
                daily = self.hist_demand.get(key, 0) / 7.0
                pf_qty = r.randint(slot["min"], slot["max"])
                if r.random() < 0.12:
                    pf_qty = r.randint(0, slot["min"] - 1)  # below min -> replenishment needed
                if item["sku"] in stockouts:
                    pf_qty = min(pf_qty, max(0, open_qty // 3))
                self._add_inv(dc_id, slot["loc"]["location_id"], item, pf_qty, life,
                              allocated=min(open_qty, pf_qty + (15 if r.random() < 0.08 else 0)))
                if item["sku"] in stockouts:
                    continue
                target = int(daily * r.uniform(5, 14)) + open_qty
                while target > 0 and pool[item["temp_zone"]]:
                    qty = min(target, r.randint(150, 240))
                    loc = pool[item["temp_zone"]].pop()
                    self._add_inv(dc_id, loc["location_id"], item, qty, life, reserve=True)
                    target -= qty

            # Planted data-integrity anomalies for the inventory-integrity agent.
            dc_inv = [x for x in self.rows["inventory"] if x["dc_id"] == dc_id]
            faces = [x for x in dc_inv if self.locations[x["location_id"]]["location_type"] == "PICK"]
            neg = r.choice(faces)
            neg.update(qty_on_hand=-4, qty_allocated=0)  # negative on-hand after an unconfirmed pick
            over = r.choice([x for x in faces if x is not neg])
            over.update(qty_on_hand=over_cap(self.locations[over["location_id"]]))  # exceeds slot capacity
            cold = next((i for i in items if i["temp_zone"] != "DRY"), None)
            dry_res = spare_dry
            if cold:  # chilled/frozen product sitting in an ambient reserve slot
                self._add_inv(dc_id, dry_res["location_id"], cold, r.randint(20, 60), cold["shelf_life_days"],
                              reserve=True)

    def _emit_order(self, dc_id, cust, lines, order_date, ship_date, wave_id, w_status, day_kind, released,
                    pickers, alloc):
        r = self.r
        order_id = self.nid(f"O{dc_id}", 7)
        if day_kind == "past":
            status = "SHIPPED"
        else:
            status = r.choice(["PICKING", "PICKING", "PICKED"]) if w_status == "IN_PROGRESS" else "RELEASED"
        total_cases = sum(q for _l, _i, q in lines)
        self.add("outbound_orders", order_id=order_id, dc_id=dc_id, customer_id=cust["customer_id"],
                 route_id=cust["route_id"], order_date=order_date.isoformat(), ship_date=ship_date.isoformat(),
                 wave_id=wave_id, status=status,
                 priority=r.choices([1, 2, 3], weights=[0.1, 0.3, 0.6])[0], total_lines=len(lines),
                 total_cases=total_cases)
        picker_pool = [p for p in pickers if p["shift"] == "NIGHT"] or pickers
        t = released + timedelta(minutes=r.randint(10, 120))
        for ln, item, qty in lines:
            slot = self.pick_loc[(dc_id, item["sku"])]
            loc = slot["loc"]
            zone_pickers = [p for p in picker_pool if p["home_zone"] == item["temp_zone"]] or picker_pool
            assoc = r.choice(zone_pickers)
            rate = next(s[2] for s in LABOR_STANDARDS if s[0] == "PICKER" and s[1] == item["temp_zone"])
            t += timedelta(seconds=3600 * qty / (rate * assoc["_perf"]) / 4)
            done = status in ("SHIPPED", "PICKED") or (status == "PICKING" and t <= self.now and r.random() < 0.7)
            if done and day_kind == "inflight" and t > self.now:
                t = self.now - timedelta(minutes=r.randint(1, 30))
            picked, short, reason = qty, 0, None
            if done and r.random() < 0.025:
                short = r.randint(1, qty)
                picked = qty - short
                reason = r.choices(["NO_STOCK", "PICK_FACE_EMPTY", "STOCK_ON_HOLD", "DAMAGED"],
                                   weights=[0.35, 0.4, 0.15, 0.1])[0]
            if not done:
                picked = 0
                alloc[(dc_id, item["sku"])] = alloc.get((dc_id, item["sku"]), 0) + qty
            if day_kind == "past" and (self.as_of - ship_date).days < 7:
                self.hist_demand[(dc_id, item["sku"])] = self.hist_demand.get((dc_id, item["sku"]), 0) + qty
            self.add("order_lines", order_id=order_id, line_number=ln, dc_id=dc_id, sku=item["sku"],
                     qty_ordered=qty, qty_picked=picked, qty_short=short, short_reason=reason)
            if done:
                tstatus = "SHORT" if short else "COMPLETE"
            else:
                tstatus = "IN_PROGRESS" if status == "PICKING" and r.random() < 0.3 else (
                    "ASSIGNED" if status == "PICKING" else "OPEN")
            self.add("pick_tasks", task_id=self.nid("T", 8), dc_id=dc_id, wave_id=wave_id, order_id=order_id,
                     line_number=ln, sku=item["sku"], location_id=loc["location_id"], qty=qty, qty_picked=picked,
                     associate_id=assoc["associate_id"] if tstatus != "OPEN" else None, status=tstatus,
                     created_at=_dt(released), completed_at=_dt(t) if done else None,
                     travel_ft=round(loc["distance_to_dock_ft"] * 2, 1))


    def build_labor(self):
        """Daily labor activity derived from pick tasks, plus schedules (with call-outs)."""
        r = self.r
        cases: dict[tuple[str, str, str], int] = {}
        assoc_by_id = {a["associate_id"]: a for lst in self.associates.values() for a in lst}
        task_day = {}
        for t in self.rows["pick_tasks"]:
            if t["status"] in ("COMPLETE", "SHORT") and t["associate_id"]:
                d = t["completed_at"][:10]
                key = (t["associate_id"], d, self.item_by_sku[t["sku"]]["temp_zone"])
                cases[key] = cases.get(key, 0) + t["qty_picked"]
                task_day[(t["associate_id"], d)] = True
        std = {(s[0], s[1]): s[2] for s in LABOR_STANDARDS}
        for (aid, d, zone), n in cases.items():
            a = assoc_by_id[aid]
            hours = n / (std[("PICKER", zone)] * a["_perf"])
            self.add("labor_activity", activity_id=self.nid("LA"), dc_id=a["dc_id"], associate_id=aid, work_date=d,
                     role="PICKER", zone=zone, cases_handled=n, direct_hours=round(hours, 2),
                     indirect_hours=round(r.uniform(0.3, 1.2) * min(1, hours / 6), 2))
        # Non-picker roles: synthetic daily throughput.
        for dc_id, assoc in self.associates.items():
            for a in assoc:
                if a["role"] == "PICKER":
                    continue
                for back in range(1, 15):
                    d = self.as_of - timedelta(days=back)
                    if r.random() < 0.25:
                        continue
                    hours = round(r.uniform(6.5, 9.5), 2)
                    rate = std[(a["role"], a["home_zone"])] * a["_perf"]
                    self.add("labor_activity", activity_id=self.nid("LA"), dc_id=dc_id,
                             associate_id=a["associate_id"], work_date=d.isoformat(), role=a["role"],
                             zone=a["home_zone"], cases_handled=int(rate * hours), direct_hours=hours,
                             indirect_hours=round(r.uniform(0.4, 1.4), 2))
            # Schedules today/tomorrow. Tonight's night shift (picks tomorrow's routes) at one DC per WMS
            # platform gets extra call-outs.
            heavy_callout = dc_id in ("MTX", "FDL")
            for back in (0, 1):
                d = self.as_of + timedelta(days=back)
                kept = 0
                for a in assoc:
                    status = r.choices(["SCHEDULED", "PTO", "CALLOUT"], weights=[0.88, 0.07, 0.05])[0]
                    if back == 0 and heavy_callout and a["shift"] == "NIGHT" and a["role"] == "PICKER":
                        # Flu wave: only two night pickers made it in tonight.
                        status = "SCHEDULED" if kept < 2 else "CALLOUT"
                        kept += status == "SCHEDULED"
                    self.add("labor_schedule", dc_id=dc_id, associate_id=a["associate_id"], work_date=d.isoformat(),
                             shift=a["shift"], scheduled_hours=8.0, status=status)

    def build_dock(self):
        r = self.r
        for dc_id, *_ in DCS:
            doors = self.doors[dc_id]
            ib = [d for d in doors if d["door_type"] == "INBOUND"]
            ob = [d for d in doors if d["door_type"] == "OUTBOUND"]
            items = self.dc_items[dc_id]
            for back in (-2, -1, 0, 1):
                day = self.as_of + timedelta(days=back)
                # Inbound: ~18 supplier deliveries/day between 06:00 and 16:00.
                door_free = {d["door_id"]: datetime.combine(day, time(5, 0)) for d in ib}
                for k in range(18):
                    zone = r.choices(["DRY", "COOLER", "FREEZER"], weights=[0.55, 0.22, 0.23])[0]
                    start = datetime.combine(day, time(6, 0)) + timedelta(minutes=30 * k + r.choice([0, 15]))
                    end = start + timedelta(minutes=r.choice([60, 90, 120]))
                    cands = [d for d in ib if (d["temp_capable"] or zone == "DRY") and door_free[d["door_id"]] <= start]
                    door = (cands or ib)[0]
                    door_free[door["door_id"]] = end
                    appt = self.nid(f"AP{dc_id}", 5)
                    asn = self.nid("ASN", 7)
                    supplier = r.choice(SUPPLIERS)
                    arrival, status, done, assigned = self._appt_status(day, start, end)
                    self.add("dock_appointments", appointment_id=appt, dc_id=dc_id, door_id=door["door_id"],
                             direction="INBOUND", carrier=r.choice(CARRIERS), reference_id=asn, temp_zone=zone,
                             scheduled_start=_dt(start), scheduled_end=_dt(end), actual_arrival=_dt(arrival),
                             door_assigned_at=_dt(assigned), completed_at=_dt(done), status=status)
                    pallets = r.randint(6, 26)
                    asn_status = {"COMPLETED": "RECEIVED", "AT_DOOR": "RECEIVING", "CHECKED_IN": "ARRIVED",
                                  "SCHEDULED": "SCHEDULED", "NO_SHOW": "SCHEDULED"}[status]
                    lines = r.sample([i for i in items if i["temp_zone"] == zone] or items, k=r.randint(3, 8))
                    total = 0
                    for ln, it in enumerate(lines, start=1):
                        exp_cases = r.randint(40, 200)
                        total += exp_cases
                        rec = exp_cases if asn_status == "RECEIVED" else (exp_cases // 2 if asn_status == "RECEIVING" else 0)
                        self.add("asn_lines", asn_id=asn, line_number=ln, dc_id=dc_id, sku=it["sku"],
                                 cases_expected=exp_cases, cases_received=rec)
                    self.add("inbound_shipments", asn_id=asn, dc_id=dc_id, po_number=f"PO{r.randint(4000000, 4999999)}",
                             supplier=supplier, appointment_id=appt, expected_date=day.isoformat(), temp_zone=zone,
                             pallets=pallets, cases=total, status=asn_status)
                # Outbound: one load per route, door assigned 2h before departure.
                for k, route in enumerate(self.routes[dc_id]):
                    dep = datetime.combine(day, time.fromisoformat(route["departure_time"]))
                    start, end = dep - timedelta(hours=2), dep
                    door = ob[4 + (k % 12)]  # multi-temp trailers use temp-capable doors
                    appt = self.nid(f"AP{dc_id}", 5)
                    arrival, status, done, assigned = self._appt_status(day, start, end, outbound=True)
                    self.add("dock_appointments", appointment_id=appt, dc_id=dc_id, door_id=door["door_id"],
                             direction="OUTBOUND", carrier="McLane Fleet", reference_id=route["route_id"],
                             temp_zone="FREEZER", scheduled_start=_dt(start), scheduled_end=_dt(end),
                             actual_arrival=_dt(arrival), door_assigned_at=_dt(assigned), completed_at=_dt(done),
                             status=status)

            # Planted exceptions for today at this DC.
            today_ib = [a for a in self.rows["dock_appointments"]
                        if a["dc_id"] == dc_id and a["direction"] == "INBOUND"
                        and a["scheduled_start"].startswith(self.as_of.isoformat())]
            if len(today_ib) >= 6:
                late = today_ib[2]  # late carrier: arrived 95 minutes after slot
                s = datetime.fromisoformat(late["scheduled_start"])
                late.update(actual_arrival=_dt(s + timedelta(minutes=95)), status="CHECKED_IN",
                            door_assigned_at=None, completed_at=None)
                # The late trailer carries the SKUs tonight's waves are short on.
                asn_row = next(x for x in self.rows["inbound_shipments"] if x["asn_id"] == late["reference_id"])
                asn_row["status"] = "ARRIVED"
                n = sum(1 for x in self.rows["asn_lines"] if x["asn_id"] == asn_row["asn_id"])
                for k, sku in enumerate(self.stockouts[dc_id], start=n + 1):
                    cases = self.open_demand.get((dc_id, sku), 0) + r.randint(40, 120)
                    self.add("asn_lines", asn_id=asn_row["asn_id"], line_number=k, dc_id=dc_id, sku=sku,
                             cases_expected=cases, cases_received=0)
                    asn_row["cases"] += cases
                for x in self.rows["asn_lines"]:
                    if x["asn_id"] == asn_row["asn_id"]:
                        x["cases_received"] = 0
                wait = today_ib[3]  # checked in on time but waiting > 3h for a door
                s = datetime.fromisoformat(wait["scheduled_start"])
                wait.update(actual_arrival=_dt(s - timedelta(minutes=10)), status="CHECKED_IN",
                            door_assigned_at=None, completed_at=None)
                upcoming = [a for a in today_ib if a["status"] == "SCHEDULED"]
                frozen = next((a for a in upcoming if a["temp_zone"] == "FREEZER"), None)
                dry_door = next(d for d in ib if not d["temp_capable"])
                if frozen:
                    frozen["door_id"] = dry_door["door_id"]  # temp mismatch
                    upcoming.remove(frozen)
                if len(upcoming) >= 2:  # double booking
                    a, b = upcoming[0], upcoming[1]
                    b.update(door_id=a["door_id"], scheduled_start=a["scheduled_start"],
                             scheduled_end=a["scheduled_end"])

    def _appt_status(self, day, start, end, outbound=False):
        r = self.r
        now = self.now
        if start > now:
            return None, "SCHEDULED", None, None
        if not outbound and r.random() < 0.04:
            return None, "NO_SHOW", None, None
        arrival = start + timedelta(minutes=int(r.gauss(5, 20)))
        assigned = arrival + timedelta(minutes=r.randint(5, 40))
        done = end + timedelta(minutes=r.randint(-15, 45))
        if done > now:
            return arrival, "AT_DOOR", None, assigned
        return arrival, "COMPLETED", done, assigned

    def build_cycle_counts(self):
        r = self.r
        inv_by_dc: dict[str, list[dict]] = {}
        for row in self.rows["inventory"]:
            inv_by_dc.setdefault(row["dc_id"], []).append(row)
        for dc_id, rows in inv_by_dc.items():
            counters = [a["associate_id"] for a in self.associates[dc_id] if a["role"] == "FORKLIFT"]
            hot = r.sample(rows, k=4)  # a few repeat offenders with chronic variance
            for back in range(1, 8):
                d = self.as_of - timedelta(days=back)
                for row in r.sample(rows, k=12) + hot[: r.randint(0, 3)]:
                    sysq = row["qty_on_hand"]
                    if row in hot:
                        var = r.choice([-1, 1]) * r.randint(3, 12)
                    else:
                        var = 0 if r.random() < 0.92 else r.choice([-2, -1, 1, 2])
                    cost = self.item_by_sku[row["sku"]]["unit_cost"]
                    self.add("cycle_counts", count_id=self.nid("CC"), dc_id=dc_id, location_id=row["location_id"],
                             sku=row["sku"], count_date=d.isoformat(), system_qty=sysq, counted_qty=max(0, sysq + var),
                             variance_qty=var, variance_value=round(var * cost, 2), counter_id=r.choice(counters))

    def build_integration(self):
        r = self.r
        start = self.now - timedelta(hours=48)
        errors = {
            "ITEM_MASTER": [("UNKNOWN_TEMP_CLASS", "Temp class code not mapped to canonical zone"),
                            ("UOM_MISMATCH", "Case pack in message differs from item master")],
            "ASN": [("UNKNOWN_SKU", "SKU on ASN not in item master"), ("DUPLICATE_MESSAGE", "ASN already received")],
            "ORDER_RELEASE": [("ROUTE_NOT_FOUND", "Route id not configured in WMS"),
                              ("UOM_MISMATCH", "Order line UOM EA but item sells in CS")],
            "SHIP_CONFIRM": [("TIMEOUT", "Host ERP did not acknowledge within 30s")],
            "INVENTORY_SYNC": [("LOCATION_NOT_FOUND", "Location missing in canonical model")],
            "RECEIPT_CONFIRM": [("QTY_OVER_ASN", "Received quantity exceeds ASN tolerance")],
        }
        skus = [i["sku"] for i in self.items]
        for dc_id, _n, _c, _s, _seg, system, *_ in DCS:
            msgs = SOURCE_MESSAGES[system]
            for h in range(48):
                ts = start + timedelta(hours=h)
                for _ in range(int(r.uniform(6, 14) * self.scale) + 1):
                    iface = r.choice(list(msgs))
                    err_rate = 0.02
                    spike = dc_id == "MCA" and iface == "ORDER_RELEASE" and 30 <= h <= 40
                    if spike:
                        err_rate = 0.55
                    status = "SUCCESS"
                    code = detail = None
                    if r.random() < err_rate:
                        status = r.choice(["ERROR", "ERROR", "RETRY"])
                        code, detail = (("UOM_MISMATCH", "Order line UOM EA but item sells in CS") if spike
                                        else r.choice(errors[iface]))
                    self.add("wms_integration_events", event_id=self.nid("EV", 8), dc_id=dc_id, source_system=system,
                             interface=iface, source_message_type=msgs[iface],
                             event_time=_dt(ts + timedelta(minutes=r.randint(0, 59))), status=status,
                             error_code=code, error_detail=detail, reference_id=r.choice(skus))

    def run(self):
        self.build_masters()
        self.build_network()
        self.build_facility()
        self.build_orders()
        self.build_inventory()
        self.build_labor()
        self.build_dock()
        self.build_cycle_counts()
        self.build_integration()
        return self.rows


def over_cap(loc):
    return loc["capacity_cases"] + 25


def _dt(v):
    return v.strftime("%Y-%m-%d %H:%M:%S") if v else None


def write_csvs(rows: dict[str, list[dict]], out: Path):
    out.mkdir(parents=True, exist_ok=True)
    for table, data in rows.items():
        cols = columns(table)
        with open(out / f"{table}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for row in data:
                w.writerow({c: ("" if row.get(c) is None else row.get(c)) for c in cols})


def generate(out: Path, as_of: date = DEFAULT_AS_OF, scale: float = 1.0, seed: int = 27) -> dict[str, int]:
    rows = Gen(as_of, scale, seed).run()
    write_csvs(rows, out)
    return {t: len(v) for t, v in rows.items()}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="data", type=Path)
    p.add_argument("--as-of", default=DEFAULT_AS_OF.isoformat(), help="Anchor 'today' date (YYYY-MM-DD)")
    p.add_argument("--scale", default=1.0, type=float, help="Volume multiplier (0.2 for a quick test set)")
    p.add_argument("--seed", default=27, type=int)
    a = p.parse_args()
    counts = generate(a.out, date.fromisoformat(a.as_of), a.scale, a.seed)
    width = max(map(len, counts))
    for t, n in counts.items():
        print(f"{t:<{width}}  {n:>8,}")
    print(f"\nWrote {sum(counts.values()):,} rows to {a.out}/")


if __name__ == "__main__":
    main()
