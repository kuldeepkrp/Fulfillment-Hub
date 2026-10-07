from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "fulfillment_hub.db"

RNG = random.Random(42)

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Rahul", "Amit", "Karan",
    "Vikram", "Ankit", "Priya", "Ananya", "Neha", "Pooja", "Sneha", "Kavya",
    "Isha", "Meera", "Riya", "Simran", "Nisha", "Varun", "Sahil", "Tanya",
]
LAST_NAMES = [
    "Sharma", "Verma", "Singh", "Kumar", "Gupta", "Patel", "Mehta", "Jain",
    "Shah", "Mishra", "Yadav", "Joshi", "Das", "Malhotra", "Chopra",
]
COURIERS = ["Delhivery", "BlueDart", "Xpressbees"]
STATUSES = ["Received", "Processing", "Picking", "Packing", "Staged", "Shipped"]
SKU_CATALOG = [
    ("P001", "TSHIRT-RED-M", "Classic T-Shirt", "Apparel", "Red / M"),
    ("P002", "TSHIRT-BLU-L", "Classic T-Shirt", "Apparel", "Blue / L"),
    ("P003", "SHOE-BLK-42", "Running Shoes", "Footwear", "Black / 42"),
    ("P004", "SHOE-WHT-41", "Running Shoes", "Footwear", "White / 41"),
    ("P005", "BAG-BLK-01", "Travel Backpack", "Bags", "Black"),
    ("P006", "CAP-NAV-01", "Sports Cap", "Accessories", "Navy"),
    ("P007", "MUG-WHT-01", "Ceramic Mug", "Home", "White"),
    ("P008", "BOT-BLU-01", "Water Bottle", "Accessories", "Blue"),
    ("P009", "JKT-GRN-M", "Light Jacket", "Apparel", "Green / M"),
    ("P010", "WAL-BRN-01", "Leather Wallet", "Accessories", "Brown"),
]


def customer_name() -> str:
    return f"{RNG.choice(FIRST_NAMES)} {RNG.choice(LAST_NAMES)}"


def create_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS activity_log;
        DROP TABLE IF EXISTS issues;
        DROP TABLE IF EXISTS shipments;
        DROP TABLE IF EXISTS transfers;
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS inventory;
        DROP TABLE IF EXISTS warehouses;
        DROP TABLE IF EXISTS products;

        CREATE TABLE products (
            product_id TEXT PRIMARY KEY,
            sku TEXT UNIQUE NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT,
            variant TEXT
        );

        CREATE TABLE warehouses (
            warehouse_id TEXT PRIMARY KEY,
            warehouse_name TEXT NOT NULL,
            location TEXT,
            is_primary INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE inventory (
            inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id TEXT NOT NULL,
            sku TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            reserved_quantity INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
            FOREIGN KEY (sku) REFERENCES products(sku),
            UNIQUE (warehouse_id, sku)
        );

        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            order_date TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            priority TEXT NOT NULL CHECK(priority IN ('High', 'Normal')),
            deadline TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Received', 'Processing', 'Picking', 'Packing', 'Staged', 'Shipped')),
            courier TEXT NOT NULL,
            tracking_number TEXT
        );

        CREATE TABLE order_items (
            order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            sku TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (sku) REFERENCES products(sku)
        );

        CREATE TABLE transfers (
            transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            from_warehouse TEXT NOT NULL,
            to_warehouse TEXT NOT NULL,
            order_id TEXT,
            status TEXT NOT NULL CHECK(status IN ('Pending', 'Completed', 'Cancelled')),
            created_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE shipments (
            shipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            courier TEXT NOT NULL,
            pickup_time TEXT NOT NULL,
            staging_location TEXT,
            status TEXT NOT NULL CHECK(status IN ('Awaiting Pickup', 'Picked Up', 'Missed Pickup'))
        );

        CREATE TABLE issues (
            issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            issue_type TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT NOT NULL CHECK(priority IN ('High', 'Medium', 'Low')),
            status TEXT NOT NULL CHECK(status IN ('Open', 'In Progress', 'Resolved')),
            assigned_to TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT
        );

        CREATE TABLE activity_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            action TEXT NOT NULL,
            old_status TEXT,
            new_status TEXT,
            user TEXT,
            timestamp TEXT NOT NULL
        );
        """
    )
    conn.commit()


def seed_products(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO products(product_id, sku, product_name, category, variant) VALUES (?, ?, ?, ?, ?)",
        SKU_CATALOG,
    )


def seed_warehouses(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO warehouses(warehouse_id, warehouse_name, location, is_primary) VALUES (?, ?, ?, ?)",
        [
            ("WH01", "Main Warehouse", "Primary Location", 1),
            ("WH02", "Secondary Warehouse", "Nearby Storage", 0),
        ],
    )


def seed_inventory(conn: sqlite3.Connection) -> None:
    # Deliberate demo scenarios:
    # SHOE-BLK-42 has no stock in Main but plenty in Secondary -> transfer scenario.
    # BOT-BLU-01 is very low in Main -> low stock scenario.
    # WAL-BRN-01 is available in Main.
    main = {
        "TSHIRT-RED-M": (40, 5),
        "TSHIRT-BLU-L": (25, 3),
        "SHOE-BLK-42": (0, 0),
        "SHOE-WHT-41": (8, 2),
        "BAG-BLK-01": (18, 4),
        "CAP-NAV-01": (30, 2),
        "MUG-WHT-01": (50, 5),
        "BOT-BLU-01": (3, 1),
        "JKT-GRN-M": (6, 1),
        "WAL-BRN-01": (15, 2),
    }
    secondary = {
        "TSHIRT-RED-M": (20, 0),
        "TSHIRT-BLU-L": (15, 0),
        "SHOE-BLK-42": (12, 0),
        "SHOE-WHT-41": (5, 0),
        "BAG-BLK-01": (10, 0),
        "CAP-NAV-01": (10, 0),
        "MUG-WHT-01": (25, 0),
        "BOT-BLU-01": (20, 0),
        "JKT-GRN-M": (8, 0),
        "WAL-BRN-01": (5, 0),
    }
    rows = []
    for sku, (qty, reserved) in main.items():
        rows.append(("WH01", sku, qty, reserved))
    for sku, (qty, reserved) in secondary.items():
        rows.append(("WH02", sku, qty, reserved))
    conn.executemany(
        "INSERT INTO inventory(warehouse_id, sku, quantity, reserved_quantity) VALUES (?, ?, ?, ?)",
        rows,
    )


def generate_orders() -> tuple[list[tuple], list[tuple]]:
    now = datetime.now().replace(microsecond=0)
    orders: list[tuple] = []
    items: list[tuple] = []

    # Orders 1001-1008 are deliberately designed around the transfer workflow.
    forced = {
        1: ("High", "Processing", "SHOE-BLK-42", 1, 45),
        2: ("High", "Picking", "SHOE-BLK-42", 1, 75),
        3: ("High", "Processing", "SHOE-BLK-42", 2, 100),
        4: ("Normal", "Received", "SHOE-BLK-42", 1, 160),
        5: ("High", "Picking", "SHOE-BLK-42", 1, -20),
        6: ("Normal", "Processing", "SHOE-BLK-42", 2, -45),
        7: ("High", "Packing", "SHOE-WHT-41", 1, 240),
        8: ("Normal", "Staged", "BAG-BLK-01", 1, 300),
    }

    for i in range(1, 251):
        order_id = f"ORD-{1000 + i}"
        order_time = now - timedelta(minutes=RNG.randint(20, 720))

        if i in forced:
            priority, status, sku, qty, deadline_offset = forced[i]
            deadline = now + timedelta(minutes=deadline_offset)
            selected_skus = [sku]
            quantities = [qty]
        else:
            priority = "High" if RNG.random() < 0.15 else "Normal"
            status = RNG.choices(
                STATUSES,
                weights=[8, 10, 15, 15, 15, 37],
                k=1,
            )[0]
            deadline_hours = RNG.choice([2, 3, 4]) if priority == "High" else RNG.choice([5, 6, 8, 10])
            deadline = order_time + timedelta(hours=deadline_hours)
            selected_skus = RNG.sample([x[1] for x in SKU_CATALOG], RNG.randint(1, 3))
            quantities = [RNG.randint(1, 2) for _ in selected_skus]

        tracking = f"TRK{RNG.randint(10000000, 99999999)}" if status == "Shipped" else None
        courier = RNG.choice(COURIERS)

        orders.append(
            (
                order_id,
                order_time.isoformat(sep=" "),
                customer_name(),
                priority,
                deadline.isoformat(sep=" "),
                status,
                courier,
                tracking,
            )
        )

        for sku, qty in zip(selected_skus, quantities):
            items.append((order_id, sku, qty))

    return orders, items


def seed_orders(conn: sqlite3.Connection) -> tuple[list[str], list[str]]:
    orders, items = generate_orders()
    conn.executemany(
        """INSERT INTO orders(order_id, order_date, customer_name, priority, deadline, status, courier, tracking_number)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        orders,
    )
    conn.executemany(
        "INSERT INTO order_items(order_id, sku, quantity) VALUES (?, ?, ?)",
        items,
    )
    transfer_order_ids = [f"ORD-{1000 + i}" for i in range(1, 7)]
    return transfer_order_ids, [f"ORD-{1000 + i}" for i in range(1, 251)]


def seed_transfers(conn: sqlite3.Connection, transfer_orders: list[str]) -> None:
    now = datetime.now().replace(microsecond=0)
    rows = []
    for order_id in transfer_orders:
        qty = conn.execute(
            "SELECT quantity FROM order_items WHERE order_id = ? AND sku = 'SHOE-BLK-42' LIMIT 1",
            (order_id,),
        ).fetchone()[0]
        rows.append(
            (
                "SHOE-BLK-42",
                qty,
                "WH02",
                "WH01",
                order_id,
                "Pending",
                (now - timedelta(minutes=RNG.randint(5, 90))).isoformat(sep=" "),
                None,
            )
        )
    rows.extend(
        [
            ("SHOE-BLK-42", 1, "WH02", "WH01", "ORD-1007", "Completed", (now - timedelta(hours=2)).isoformat(sep=" "), (now - timedelta(hours=1, minutes=50)).isoformat(sep=" ")),
            ("BAG-BLK-01", 1, "WH02", "WH01", "ORD-1008", "Completed", (now - timedelta(hours=3)).isoformat(sep=" "), (now - timedelta(hours=2, minutes=45)).isoformat(sep=" ")),
        ]
    )
    conn.executemany(
        """INSERT INTO transfers(sku, quantity, from_warehouse, to_warehouse, order_id, status, created_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )


def seed_shipments(conn: sqlite3.Connection) -> None:
    now = datetime.now().replace(microsecond=0)
    rows = []
    staged_or_shipped = conn.execute(
        "SELECT order_id, courier, status FROM orders WHERE status IN ('Packing', 'Staged', 'Shipped') ORDER BY order_id LIMIT 70"
    ).fetchall()
    for idx, (order_id, courier, status) in enumerate(staged_or_shipped, start=1):
        if status == "Shipped":
            pickup_status = "Picked Up"
        elif idx % 13 == 0:
            pickup_status = "Missed Pickup"
        else:
            pickup_status = "Awaiting Pickup"
        pickup_offset = 30 if idx % 3 == 0 else 90
        pickup_time = now + timedelta(minutes=pickup_offset)
        location = f"STAGE-{chr(65 + (idx % 3))}-{(idx % 12) + 1:02d}"
        rows.append((order_id, courier, pickup_time.isoformat(sep=" "), location, pickup_status))
    conn.executemany(
        "INSERT INTO shipments(order_id, courier, pickup_time, staging_location, status) VALUES (?, ?, ?, ?, ?)",
        rows,
    )


def seed_issues(conn: sqlite3.Connection) -> None:
    now = datetime.now().replace(microsecond=0)
    issues = [
        ("ORD-1001", "Inventory", "Required SHOE-BLK-42 stock is unavailable in Main Warehouse; transfer from Secondary Warehouse is pending.", "High", "Open", "Warehouse Team", (now - timedelta(minutes=55)).isoformat(sep=" "), None),
        ("ORD-1002", "Inventory", "Required SHOE-BLK-42 stock is unavailable in Main Warehouse; transfer from Secondary Warehouse is pending.", "High", "In Progress", "Warehouse Team", (now - timedelta(minutes=40)).isoformat(sep=" "), None),
        ("ORD-1003", "Inventory", "Required SHOE-BLK-42 stock is unavailable in Main Warehouse; transfer from Secondary Warehouse is pending.", "High", "Open", "Warehouse Team", (now - timedelta(minutes=30)).isoformat(sep=" "), None),
        ("ORD-1015", "Wrong SKU", "Picker selected a different variant during verification.", "High", "Open", "Picking Team", (now - timedelta(minutes=25)).isoformat(sep=" "), None),
        ("ORD-1028", "Staging", "Packed box could not be found at the assigned staging location.", "Medium", "Open", "Warehouse Team", (now - timedelta(minutes=35)).isoformat(sep=" "), None),
        ("ORD-1039", "Courier Pickup", "Courier did not collect the package during the scheduled pickup window.", "High", "Open", "Office Team", (now - timedelta(minutes=90)).isoformat(sep=" "), None),
        ("ORD-1047", "Inventory", "System quantity did not match the physical shelf count.", "Medium", "Resolved", "Warehouse Team", (now - timedelta(hours=4)).isoformat(sep=" "), (now - timedelta(hours=3)).isoformat(sep=" ")),
        ("ORD-1058", "Wrong SKU", "Variant mismatch detected before packing.", "Medium", "Resolved", "Picking Team", (now - timedelta(hours=5)).isoformat(sep=" "), (now - timedelta(hours=4, minutes=40)).isoformat(sep=" ")),
        ("ORD-1070", "Staging", "Box moved from original staging bay without an updated location.", "Low", "In Progress", "Warehouse Team", (now - timedelta(hours=2)).isoformat(sep=" "), None),
        ("ORD-1081", "Courier Pickup", "Pickup timing needs confirmation before today's cut-off.", "Medium", "Open", "Office Team", (now - timedelta(minutes=18)).isoformat(sep=" "), None),
    ]
    conn.executemany(
        """INSERT INTO issues(order_id, issue_type, description, priority, status, assigned_to, created_at, resolved_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        issues,
    )


def seed_activity(conn: sqlite3.Connection, order_ids: list[str]) -> None:
    now = datetime.now().replace(microsecond=0)
    rows = []
    for order_id in order_ids[:25]:
        rows.append((order_id, "Order created", None, "Received", "Office Team", (now - timedelta(hours=2)).isoformat(sep=" ")))
    conn.executemany(
        """INSERT INTO activity_log(order_id, action, old_status, new_status, user, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        rows,
    )


def export_csvs(conn: sqlite3.Connection) -> None:
    data_dir = BASE_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    tables = ["products", "warehouses", "inventory", "orders", "order_items", "transfers", "shipments", "issues", "activity_log"]
    for table in tables:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        cols = [d[0] for d in conn.execute(f"SELECT * FROM {table} LIMIT 0").description]
        import csv
        with (data_dir / f"{table}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            writer.writerows(rows)


def seed_database() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        create_schema(conn)
        seed_products(conn)
        seed_warehouses(conn)
        seed_inventory(conn)
        transfer_orders, all_order_ids = seed_orders(conn)
        seed_transfers(conn, transfer_orders)
        seed_shipments(conn)
        seed_issues(conn)
        seed_activity(conn, all_order_ids)
        conn.commit()
        export_csvs(conn)
    finally:
        conn.close()

    print(f"Created {DB_PATH}")
    print("Orders:", 250)
    print("Products:", len(SKU_CATALOG))
    print("Warehouses: 2")


if __name__ == "__main__":
    seed_database()
