"""
Inline DB initializer that runs on app startup.

Creates schema tables and seeds data (idempotent).
Extracted from init_db.py so it deploys with the server/ package.
"""

import random
from datetime import date, timedelta

import psycopg

# ---------------------------------------------------------------------------
# Schema — includes both original tables and driver profile tables
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS drivers (
    id                   SERIAL PRIMARY KEY,
    name                 VARCHAR(200) NOT NULL,
    phone                VARCHAR(20),
    email                VARCHAR(100),
    city                 VARCHAR(100),
    vehicle_type         VARCHAR(10) NOT NULL CHECK (vehicle_type IN ('EV', 'ICE')),
    vehicle_make         VARCHAR(100) NOT NULL,
    vehicle_model        VARCHAR(100) NOT NULL,
    vehicle_year         INTEGER,
    license_plate        VARCHAR(20) NOT NULL,
    battery_capacity_kwh NUMERIC(6,2),
    engine_displacement_cc INTEGER,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trip_logs (
    id               SERIAL PRIMARY KEY,
    driver_id        INTEGER NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    trip_date        DATE NOT NULL,
    start_hour       INTEGER NOT NULL CHECK (start_hour >= 0 AND start_hour < 24),
    distance_km      NUMERIC(8,2) NOT NULL,
    duration_min     INTEGER NOT NULL,
    avg_speed_kmh    NUMERIC(6,2),
    max_speed_kmh    NUMERIC(6,2),
    hard_brakes      INTEGER DEFAULT 0,
    rapid_accels     INTEGER DEFAULT 0,
    fuel_or_energy   NUMERIC(8,3),
    highway_pct      NUMERIC(5,2) DEFAULT 0,
    night_driving    BOOLEAN DEFAULT FALSE,
    idle_time_min    INTEGER DEFAULT 0,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vehicle_health (
    id               SERIAL PRIMARY KEY,
    driver_id        INTEGER NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    week_date        DATE NOT NULL,
    brake_wear_pct   NUMERIC(5,2),
    tyre_fl_psi      NUMERIC(5,2),
    tyre_fr_psi      NUMERIC(5,2),
    tyre_rl_psi      NUMERIC(5,2),
    tyre_rr_psi      NUMERIC(5,2),
    battery_soh_pct  NUMERIC(5,2),
    battery_soc_pct  NUMERIC(5,2),
    engine_health_pct NUMERIC(5,2),
    oil_life_pct     NUMERIC(5,2),
    coolant_temp_c   NUMERIC(5,1),
    UNIQUE(driver_id, week_date)
);

CREATE TABLE IF NOT EXISTS driver_scores (
    id                  SERIAL PRIMARY KEY,
    driver_id           INTEGER NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    week_date           DATE NOT NULL,
    overall_score       NUMERIC(5,2),
    safety_score        NUMERIC(5,2),
    efficiency_score    NUMERIC(5,2),
    eco_score           NUMERIC(5,2),
    consistency_score   NUMERIC(5,2),
    risk_band           VARCHAR(20),
    premium_multiplier  NUMERIC(4,2),
    UNIQUE(driver_id, week_date)
);

CREATE INDEX IF NOT EXISTS idx_trip_driver_dt ON trip_logs (driver_id, trip_date);
CREATE INDEX IF NOT EXISTS idx_vh_driver_dt ON vehicle_health (driver_id, week_date);
CREATE INDEX IF NOT EXISTS idx_ds_driver_dt ON driver_scores (driver_id, week_date);
"""

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

CENTERS = [
    ("AutoPrime Mahadevpura",       "Karnataka", "Bengaluru", "Mahadevpura",  "No.12, EPIP Zone, Mahadevpura, Bengaluru 560048",  "+91 80 2845 1200", "mahadevpura@autoprime.in",  10),
    ("SwiftServ Mahadevpura",       "Karnataka", "Bengaluru", "Mahadevpura",  "Plot 7, Graphite India Road, Mahadevpura 560048",  "+91 80 2846 3300", "swift.mhd@swiftserv.in",    8),
    ("Koramangala Auto Hub",        "Karnataka", "Bengaluru", "Koramangala",  "80 Feet Road, 6th Block, Koramangala 560095",      "+91 80 2553 4400", "kora@autohub.in",           12),
    ("SouthServ Koramangala",       "Karnataka", "Bengaluru", "Koramangala",  "1st Main, 4th Block, Koramangala 560034",          "+91 80 2554 5500", "southserv.kora@gmail.com",  10),
    ("TechPark Auto Whitefield",    "Karnataka", "Bengaluru", "Whitefield",   "ITPL Main Road, Whitefield, Bengaluru 560066",     "+91 80 6677 8800", "whitefield@techparkauto.in", 14),
    ("Jayanagar Auto Hub",          "Karnataka", "Bengaluru", "Jayanagar",    "30th Cross, 4th Block, Jayanagar 560041",          "+91 80 2664 9900", "jayanagar@autohub.in",      10),
    ("NorthAuto Rajajinagar",       "Karnataka", "Bengaluru", "Rajajinagar",  "19th Cross, Rajajinagar, Bengaluru 560010",        "+91 80 2335 0011", "rajajinagar@northauto.in",  10),
    ("Indiranagar Motors",          "Karnataka", "Bengaluru", "Indiranagar",  "100 Feet Road, HAL 2nd Stage, Indiranagar 560038", "+91 80 2521 1122", "indiranagar@motors.in",     12),
    ("Andheri Auto Hub",            "Maharashtra", "Mumbai", "Andheri",       "Western Express Hwy, Andheri East, Mumbai 400069", "+91 22 2683 2200", "andheri@autohub.in",        12),
    ("Bandra Service Centre",       "Maharashtra", "Mumbai", "Bandra",        "Turner Road, Bandra West, Mumbai 400050",          "+91 22 2645 3300", "bandra@servicecentre.in",   10),
    ("Borivali Auto Works",         "Maharashtra", "Mumbai", "Borivali",      "Chandavarkar Road, Borivali West, Mumbai 400092",  "+91 22 2891 4400", "borivali@autoworks.in",     10),
    ("Kothrud Auto Hub",            "Maharashtra", "Pune", "Kothrud",         "Karve Road, Kothrud, Pune 411038",                 "+91 20 2544 5500", "kothrud@autohub.in",        12),
    ("Hadapsar Service Centre",     "Maharashtra", "Pune", "Hadapsar",        "Magarpatta Road, Hadapsar, Pune 411028",           "+91 20 2688 6600", "hadapsar@servicecentre.in", 10),
    ("Lajpat Auto Hub",             "Delhi", "Delhi", "Lajpat Nagar",         "Ring Road, Lajpat Nagar II, New Delhi 110024",     "+91 11 2982 7700", "lajpat@autohub.in",         12),
    ("Rohini Motors",               "Delhi", "Delhi", "Rohini",               "Sector 14, Rohini, New Delhi 110085",              "+91 11 2704 8800", "rohini@motors.in",          10),
    ("Dwarka Auto Centre",          "Delhi", "Delhi", "Dwarka",               "Sector 10, Dwarka, New Delhi 110075",              "+91 11 2508 9900", "dwarka@autocentre.in",      10),
    ("Janakpuri Service Hub",       "Delhi", "Delhi", "Janakpuri",            "C-Block, Janakpuri, New Delhi 110058",             "+91 11 2552 0011", "janakpuri@servicehub.in",   10),
    ("Saket Auto Works",            "Delhi", "Delhi", "Saket",                "Press Enclave Road, Saket, New Delhi 110017",      "+91 11 2956 1122", "saket@autoworks.in",        8),
    ("T Nagar Auto Hub",            "Tamil Nadu", "Chennai", "T Nagar",        "Usman Road, T Nagar, Chennai 600017",             "+91 44 2434 2200", "tnagar@autohub.in",         12),
    ("Velachery Motors",            "Tamil Nadu", "Chennai", "Velachery",      "Velachery Main Road, Chennai 600042",             "+91 44 2244 3300", "velachery@motors.in",       10),
    ("Anna Nagar Auto Centre",      "Tamil Nadu", "Chennai", "Anna Nagar",     "2nd Avenue, Anna Nagar, Chennai 600040",          "+91 44 2626 4400", "annanagar@autocentre.in",   12),
    ("Adyar Service Hub",           "Tamil Nadu", "Chennai", "Adyar",          "LB Road, Adyar, Chennai 600020",                  "+91 44 2441 5500", "adyar@servicehub.in",       10),
    ("Porur Auto Works",            "Tamil Nadu", "Chennai", "Porur",          "Mount Poonamallee Road, Porur, Chennai 600116",   "+91 44 2476 6600", "porur@autoworks.in",        10),
    ("Banjara Hills Auto Hub",      "Telangana", "Hyderabad", "Banjara Hills",  "Road No. 12, Banjara Hills, Hyderabad 500034",   "+91 40 2354 7700", "banjara@autohub.in",        12),
    ("Kondapur Motors",             "Telangana", "Hyderabad", "Kondapur",       "Kondapur Main Road, Hyderabad 500084",           "+91 40 2311 8800", "kondapur@motors.in",        10),
    ("Secunderabad Service Centre", "Telangana", "Hyderabad", "Secunderabad",   "Trimulgherry, Secunderabad 500015",              "+91 40 2780 9900", "secunderabad@svc.in",       10),
    ("Kukatpally Auto Works",       "Telangana", "Hyderabad", "Kukatpally",     "KPHB Colony, Kukatpally, Hyderabad 500072",      "+91 40 2307 0011", "kukatpally@autoworks.in",   12),
    ("Gachibowli Motors",           "Telangana", "Hyderabad", "Gachibowli",     "DLF Cybercity, Gachibowli, Hyderabad 500032",   "+91 40 2300 1122", "gachibowli@motors.in",      14),
    ("Navrangpura Auto Hub",        "Gujarat", "Ahmedabad", "Navrangpura",      "C G Road, Navrangpura, Ahmedabad 380009",        "+91 79 2640 2200", "navrangpura@autohub.in",    10),
    ("Vastrapur Motors",            "Gujarat", "Ahmedabad", "Vastrapur",        "Vastrapur Lake Road, Ahmedabad 380015",          "+91 79 2677 3300", "vastrapur@motors.in",       10),
    ("Satellite Auto Centre",       "Gujarat", "Ahmedabad", "Satellite",        "Satellite Road, Ahmedabad 380015",               "+91 79 2693 4400", "satellite@autocentre.in",   10),
    ("Bopal Service Hub",           "Gujarat", "Ahmedabad", "Bopal",            "S P Ring Road, Bopal, Ahmedabad 380058",         "+91 79 2971 5500", "bopal@servicehub.in",       8),
    ("Vaishali Nagar Auto Hub",     "Rajasthan", "Jaipur", "Vaishali Nagar",    "Central Spine, Vaishali Nagar, Jaipur 302021",   "+91 141 2352 6600", "vaishali@autohub.in",      10),
    ("Mansarovar Motors",           "Rajasthan", "Jaipur", "Mansarovar",        "Gopalpura Bypass, Mansarovar, Jaipur 302020",    "+91 141 2395 7700", "mansarovar@motors.in",     10),
    ("Civil Lines Auto Centre",     "Rajasthan", "Jaipur", "Civil Lines",       "Station Road, Civil Lines, Jaipur 302006",       "+91 141 2376 8800", "civillines@autocentre.in", 12),
    ("Tonk Road Service Hub",       "Rajasthan", "Jaipur", "Tonk Road",         "Durgapura, Tonk Road, Jaipur 302018",            "+91 141 2708 9900", "tonkroad@servicehub.in",   10),
    ("Hazratganj Auto Hub",         "Uttar Pradesh", "Lucknow", "Hazratganj",   "Mahatma Gandhi Marg, Hazratganj, Lucknow 226001", "+91 522 2614 0011", "hazratganj@autohub.in",   10),
    ("Gomti Nagar Motors",          "Uttar Pradesh", "Lucknow", "Gomti Nagar",  "Vibhuti Khand, Gomti Nagar, Lucknow 226010",      "+91 522 2720 1122", "gomtinagar@motors.in",    12),
    ("Alambagh Service Centre",     "Uttar Pradesh", "Lucknow", "Alambagh",     "Kanpur Road, Alambagh, Lucknow 226005",           "+91 522 2456 2200", "alambagh@svc.in",         10),
    ("Aliganj Auto Works",          "Uttar Pradesh", "Lucknow", "Aliganj",      "Sector H, Aliganj, Lucknow 226024",               "+91 522 2351 3300", "aliganj@autoworks.in",    8),
    ("Park Street Auto Hub",        "West Bengal", "Kolkata", "Park Street",    "21 Park Street, Kolkata 700016",                  "+91 33 2229 4400", "parkstreet@autohub.in",   10),
    ("Salt Lake Motors",            "West Bengal", "Kolkata", "Salt Lake",      "Sector V, Salt Lake City, Kolkata 700091",        "+91 33 2357 5500", "saltlake@motors.in",      12),
    ("Behala Service Centre",       "West Bengal", "Kolkata", "Behala",         "Diamond Harbour Road, Behala, Kolkata 700034",    "+91 33 2400 6600", "behala@servicecentre.in", 10),
    ("Dum Dum Auto Works",          "West Bengal", "Kolkata", "Dum Dum",        "Jessore Road, Dum Dum, Kolkata 700028",           "+91 33 2551 7700", "dumdum@autoworks.in",     8),
]

DRIVERS = [
    ("Hussain Jagirdar", "+91 98765 43210", "hussain.j@email.in",  "Bengaluru",  "ICE", "Mahindra", "XUV700",         2024, "KA01AB1234", None,  1997),
    ("Priya Sharma",    "+91 98765 43211", "priya.s@email.in",    "Mumbai",     "EV",  "MG",       "ZS EV",          2024, "MH02CD5678", 50.3,  None),
    ("Rahul Verma",     "+91 98765 43212", "rahul.v@email.in",    "Delhi",      "EV",  "Hyundai",  "Ioniq 5",        2024, "DL03EF9012", 72.6,  None),
    ("Sneha Patel",     "+91 98765 43213", "sneha.p@email.in",    "Ahmedabad",  "EV",  "Tata",     "Tiago EV",       2023, "GJ04GH3456", 24.0,  None),
    ("Vikram Singh",    "+91 98765 43214", "vikram.s@email.in",   "Chennai",    "EV",  "BYD",      "Atto 3",         2024, "TN05IJ7890", 60.5,  None),
    ("Ananya Reddy",    "+91 98765 43215", "ananya.r@email.in",   "Hyderabad",  "EV",  "Mahindra", "XUV400 EV",      2024, "TS06KL1234", 39.4,  None),
    ("Karan Gupta",     "+91 98765 43216", "karan.g@email.in",    "Jaipur",     "EV",  "Tata",     "Punch EV",       2024, "RJ07MN5678", 35.0,  None),
    ("Meera Iyer",      "+91 98765 43217", "meera.i@email.in",    "Bengaluru",  "ICE", "Maruti",   "Swift",          2023, "KA01OP9012", None, 1197),
    ("Aditya Joshi",    "+91 98765 43218", "aditya.j@email.in",   "Pune",       "ICE", "Hyundai",  "Creta",          2024, "MH12QR3456", None, 1497),
    ("Fatima Khan",     "+91 98765 43219", "fatima.k@email.in",   "Delhi",      "ICE", "Honda",    "City",           2023, "DL08ST7890", None, 1498),
    ("Rohan Das",       "+91 98765 43220", "rohan.d@email.in",    "Kolkata",    "ICE", "Tata",     "Harrier",        2024, "WB09UV1234", None, 1956),
    ("Kavitha Nair",    "+91 98765 43221", "kavitha.n@email.in",  "Chennai",    "ICE", "Toyota",   "Innova Hycross", 2024, "TN10WX5678", None, 1987),
    ("Suresh Yadav",    "+91 98765 43222", "suresh.y@email.in",   "Lucknow",    "ICE", "Mahindra", "XUV700",         2024, "UP11YZ9012", None, 1997),
    ("Deepika Rao",     "+91 98765 43223", "deepika.r@email.in",  "Hyderabad",  "ICE", "Kia",      "Seltos",         2023, "TS12AB3456", None, 1493),
    ("Amit Chatterjee", "+91 98765 43224", "amit.c@email.in",     "Kolkata",    "ICE", "Skoda",    "Slavia",         2023, "WB13CD7890", None, 1498),
]

PERSONAS = {
    "conservative": {"speed_mean": 45, "speed_std": 8, "max_speed_cap": 100, "brake_rate": 0.3, "accel_rate": 0.2, "idle_rate": 0.05},
    "normal":       {"speed_mean": 55, "speed_std": 12, "max_speed_cap": 120, "brake_rate": 0.8, "accel_rate": 0.6, "idle_rate": 0.10},
    "aggressive":   {"speed_mean": 70, "speed_std": 18, "max_speed_cap": 155, "brake_rate": 2.0, "accel_rate": 1.8, "idle_rate": 0.15},
}

DRIVER_PERSONAS = [
    "normal", "conservative", "aggressive", "conservative", "normal",
    "aggressive", "normal", "conservative", "normal", "aggressive",
    "normal", "conservative", "aggressive", "normal", "conservative",
]


def _generate_trips(driver_idx, driver, days=60):
    rng = random.Random(42 + driver_idx)
    persona = PERSONAS[DRIVER_PERSONAS[driver_idx]]
    vehicle_type = driver[4]
    trips = []
    today = date.today()
    start_date = today - timedelta(days=days)
    for day_offset in range(days):
        trip_date = start_date + timedelta(days=day_offset)
        if rng.random() < 0.15:
            continue
        num_trips = rng.choices([1, 2, 3], weights=[0.3, 0.5, 0.2])[0]
        for _ in range(num_trips):
            start_hour = rng.choice([7, 8, 9, 10, 12, 13, 14, 17, 18, 19, 20, 21, 22])
            distance = round(rng.gauss(25, 15), 2)
            if distance < 2:
                distance = round(rng.uniform(2, 8), 2)
            avg_speed = round(max(15, rng.gauss(persona["speed_mean"], persona["speed_std"])), 2)
            max_speed = round(min(persona["max_speed_cap"], avg_speed + rng.uniform(15, 50)), 2)
            duration = round(distance / avg_speed * 60)
            if duration < 5:
                duration = 5
            hard_brakes = max(0, round(rng.gauss(persona["brake_rate"] * distance / 10, 1)))
            rapid_accels = max(0, round(rng.gauss(persona["accel_rate"] * distance / 10, 1)))
            highway_pct = round(min(100, max(0, rng.gauss(40, 25))), 2)
            night = start_hour >= 20 or start_hour < 6
            idle_min = max(0, round(rng.gauss(persona["idle_rate"] * duration, 3)))
            if vehicle_type == "EV":
                consumption = round(distance * 18.0 / 100 * rng.uniform(0.7, 1.4), 3)
            else:
                consumption = round(distance * 8.0 / 100 * rng.uniform(0.7, 1.5), 3)
            trips.append((
                driver_idx + 1, trip_date, start_hour, distance, duration,
                avg_speed, max_speed, hard_brakes, rapid_accels,
                consumption, highway_pct, night, idle_min,
            ))
    return trips


def _generate_health(driver_idx, driver, weeks=8):
    rng = random.Random(100 + driver_idx)
    vehicle_type = driver[4]
    records = []
    today = date.today()
    for w in range(weeks):
        week_date = today - timedelta(weeks=weeks - 1 - w)
        brake_wear = round(max(10, min(100, 85 - w * rng.uniform(1, 4) + rng.gauss(0, 3))), 2)
        tyre_base = rng.uniform(30, 35)
        tyres = [round(tyre_base + rng.gauss(0, 1.5), 2) for _ in range(4)]
        if vehicle_type == "EV":
            soh = round(max(80, 98 - w * rng.uniform(0.1, 0.3)), 2)
            soc = round(rng.uniform(30, 95), 2)
            records.append((driver_idx + 1, week_date, brake_wear, tyres[0], tyres[1], tyres[2], tyres[3], soh, soc, None, None, None))
        else:
            engine_health = round(max(60, 95 - w * rng.uniform(0.5, 1.5) + rng.gauss(0, 2)), 2)
            oil_life = round(max(10, 90 - w * rng.uniform(3, 8)), 2)
            coolant = round(rng.uniform(85, 100), 1)
            records.append((driver_idx + 1, week_date, brake_wear, tyres[0], tyres[1], tyres[2], tyres[3], None, None, engine_health, oil_life, coolant))
    return records


def _compute_scores(driver_idx, driver, all_trips, weeks=8):
    rng = random.Random(200 + driver_idx)
    vehicle_type = driver[4]
    driver_id = driver_idx + 1
    records = []
    today = date.today()
    for w in range(weeks):
        week_end = today - timedelta(weeks=weeks - 1 - w)
        week_start = week_end - timedelta(days=6)
        week_trips = [t for t in all_trips if t[0] == driver_id and week_start <= t[1] <= week_end]
        if not week_trips:
            continue
        total_dist = sum(t[3] for t in week_trips)
        total_brakes = sum(t[7] for t in week_trips)
        total_accels = sum(t[8] for t in week_trips)
        max_speed_seen = max(t[6] for t in week_trips)
        night_trips = sum(1 for t in week_trips if t[11])
        total_idle = sum(t[12] for t in week_trips)
        total_duration = sum(t[4] for t in week_trips)
        avg_consumption = sum(t[9] for t in week_trips) / total_dist * 100 if total_dist > 0 else 0
        speed_penalty = max(0, (max_speed_seen - 130) * 2) if max_speed_seen > 130 else 0
        brake_per_100km = total_brakes / total_dist * 100 if total_dist > 0 else 0
        brake_penalty = max(0, (brake_per_100km - 5) * 3)
        night_pct = night_trips / len(week_trips) * 100 if week_trips else 0
        night_penalty = night_pct * 0.2
        safety = round(max(10, min(100, 100 - speed_penalty - brake_penalty - night_penalty + rng.gauss(0, 2))), 2)
        baseline = 18.0 if vehicle_type == "EV" else 12.0
        eff_ratio = avg_consumption / baseline
        efficiency = round(max(10, min(100, 100 - (eff_ratio - 0.8) * 80 + rng.gauss(0, 3))), 2)
        idle_pct = total_idle / total_duration * 100 if total_duration > 0 else 0
        accel_per_100km = total_accels / total_dist * 100 if total_dist > 0 else 0
        eco = round(max(10, min(100, 100 - idle_pct * 1.5 - accel_per_100km * 2 + rng.gauss(0, 3))), 2)
        if len(week_trips) > 1:
            brake_rates = [t[7] / max(t[3], 0.1) for t in week_trips]
            mean_br = sum(brake_rates) / len(brake_rates)
            std_br = (sum((b - mean_br) ** 2 for b in brake_rates) / len(brake_rates)) ** 0.5
            consistency = round(max(10, min(100, 100 - std_br * 200 + rng.gauss(0, 3))), 2)
        else:
            consistency = round(rng.uniform(60, 85), 2)
        overall = round(safety * 0.40 + efficiency * 0.25 + eco * 0.20 + consistency * 0.15, 2)
        if overall >= 80:
            risk_band, multiplier = "Low", 0.85
        elif overall >= 60:
            risk_band, multiplier = "Medium", 1.0
        elif overall >= 40:
            risk_band, multiplier = "High", 1.25
        else:
            risk_band, multiplier = "Very High", 1.5
        records.append((driver_id, week_end, overall, safety, efficiency, eco, consistency, risk_band, multiplier))
    return records


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_init(conn: psycopg.Connection) -> None:
    """Create driver profile tables and seed data. Safe to call multiple times."""
    print("Creating driver profile schema...")
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
    conn.commit()
    print("  Schema OK")

    # One-time data fix: update KA01AB1234 to Hussain Jagirdar / Mahindra XUV700
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE drivers SET name='Hussain Jagirdar', email='hussain.j@email.in',
               vehicle_type='ICE', vehicle_make='Mahindra', vehicle_model='XUV700',
               battery_capacity_kwh=NULL, engine_displacement_cc=1997
               WHERE license_plate='KA01AB1234' AND name != 'Hussain Jagirdar'"""
        )
        if cur.rowcount:
            cur.execute(
                """UPDATE vehicle_health SET
                   battery_soh_pct=NULL, battery_soc_pct=NULL,
                   engine_health_pct=88.0, oil_life_pct=62.0, coolant_temp_c=92.0
                   WHERE driver_id = (SELECT id FROM drivers WHERE license_plate='KA01AB1234')"""
            )
            conn.commit()
            print("  Updated KA01AB1234 to Hussain Jagirdar / Mahindra XUV700")

    # Seed drivers + telemetry
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM drivers")
        if cur.fetchone()[0] > 0:
            print("  Drivers already seeded.")
            return

    print(f"Seeding {len(DRIVERS)} drivers with telemetry data...")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO drivers (name,phone,email,city,vehicle_type,vehicle_make,vehicle_model,vehicle_year,license_plate,battery_capacity_kwh,engine_displacement_cc) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            DRIVERS,
        )
    conn.commit()
    print(f"  {len(DRIVERS)} drivers inserted.")

    all_trips = []
    for i, drv in enumerate(DRIVERS):
        all_trips.extend(_generate_trips(i, drv, days=60))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO trip_logs (driver_id,trip_date,start_hour,distance_km,duration_min,avg_speed_kmh,max_speed_kmh,hard_brakes,rapid_accels,fuel_or_energy,highway_pct,night_driving,idle_time_min) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            all_trips,
        )
    conn.commit()
    print(f"  {len(all_trips)} trip logs inserted.")

    all_health = []
    for i, drv in enumerate(DRIVERS):
        all_health.extend(_generate_health(i, drv, weeks=8))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO vehicle_health (driver_id,week_date,brake_wear_pct,tyre_fl_psi,tyre_fr_psi,tyre_rl_psi,tyre_rr_psi,battery_soh_pct,battery_soc_pct,engine_health_pct,oil_life_pct,coolant_temp_c) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            all_health,
        )
    conn.commit()
    print(f"  {len(all_health)} vehicle health snapshots inserted.")

    all_scores = []
    for i, drv in enumerate(DRIVERS):
        all_scores.extend(_compute_scores(i, drv, all_trips, weeks=8))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO driver_scores (driver_id,week_date,overall_score,safety_score,efficiency_score,eco_score,consistency_score,risk_band,premium_multiplier) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            all_scores,
        )
    conn.commit()
    print(f"  {len(all_scores)} driver score records inserted.")
