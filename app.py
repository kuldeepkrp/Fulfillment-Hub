from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "fulfillment_hub.db"

st.set_page_config(
    page_title="Fulfillment Hub",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_database() -> None:
    if not DB_PATH.exists():
        from seed_database import seed_database
        seed_database()


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def execute(sql: str, params: tuple = ()) -> None:
    with get_connection() as conn:
        conn.execute(sql, params)
        conn.commit()


def scalar(sql: str, params: tuple = ()) -> int:
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
        return int(row[0]) if row and row[0] is not None else 0


def fmt_dt(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(str(value)).strftime("%d %b %Y, %I:%M %p")
    except ValueError:
        return str(value)


def urgency(priority: str, deadline: str, status: str) -> str:
    if status == "Shipped":
        return "Completed"
    try:
        deadline_dt = datetime.fromisoformat(deadline)
    except ValueError:
        return "Normal"
    if datetime.now() > deadline_dt:
        return "Overdue"
    if priority == "High":
        return "Priority"
    return "Normal"


def order_inventory(order_id: str) -> pd.DataFrame:
    sql = """
    SELECT
        oi.sku AS SKU,
        p.product_name AS Product,
        p.variant AS Variant,
        oi.quantity AS Required,
        COALESCE(m.available, 0) AS Main_Available,
        COALESCE(s.available, 0) AS Secondary_Available,
        CASE
            WHEN COALESCE(m.available, 0) >= oi.quantity THEN 'Available'
            WHEN COALESCE(m.available, 0) + COALESCE(s.available, 0) >= oi.quantity THEN 'Transfer Required'
            ELSE 'Out of Stock'
        END AS Availability,
        CASE
            WHEN COALESCE(m.available, 0) >= oi.quantity THEN 'Pick from Main'
            WHEN COALESCE(m.available, 0) + COALESCE(s.available, 0) >= oi.quantity THEN 'Transfer to Main'
            ELSE 'Raise inventory issue'
        END AS Action
    FROM order_items oi
    JOIN products p ON p.sku = oi.sku
    LEFT JOIN (
        SELECT sku, quantity - reserved_quantity AS available
        FROM inventory WHERE warehouse_id = 'WH01'
    ) m ON m.sku = oi.sku
    LEFT JOIN (
        SELECT sku, quantity - reserved_quantity AS available
        FROM inventory WHERE warehouse_id = 'WH02'
    ) s ON s.sku = oi.sku
    WHERE oi.order_id = ?
    ORDER BY oi.order_item_id
    """
    return query_df(sql, (order_id,))


def order_info(order_id: str) -> pd.Series | None:
    df = query_df("SELECT * FROM orders WHERE order_id = ?", (order_id,))
    return None if df.empty else df.iloc[0]


def fulfillment_status(order_id: str) -> str:
    inv = order_inventory(order_id)
    if inv.empty:
        return "No Items"
    statuses = set(inv["Availability"])
    if "Out of Stock" in statuses:
        return "Blocked — Out of Stock"
    if "Transfer Required" in statuses:
        return "Blocked — Transfer Required"
    return "Ready for Next Step"


def log_activity(order_id: str, action: str, old_status: str | None, new_status: str | None, user: str = "Demo User") -> None:
    execute(
        """INSERT INTO activity_log(order_id, action, old_status, new_status, user, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (order_id, action, old_status, new_status, user, datetime.now().replace(microsecond=0).isoformat(sep=" ")),
    )


def status_index(status: str) -> int:
    return {"Received": 0, "Processing": 1, "Picking": 2, "Packing": 3, "Staged": 4, "Shipped": 5}.get(status, 0)


def has_pick_verification(order_id: str) -> bool:
    return scalar(
        "SELECT COUNT(*) FROM activity_log WHERE order_id = ? AND action = 'Picking verification passed'",
        (order_id,),
    ) > 0


def can_move(order_id: str, next_status: str) -> tuple[bool, str]:
    info = order_info(order_id)
    if info is None:
        return False, "Order not found."
    current = info["status"]
    stages = ["Received", "Processing", "Picking", "Packing", "Staged", "Shipped"]
    expected_next = stages[min(status_index(current) + 1, len(stages) - 1)]
    if next_status != expected_next:
        return False, f"The next allowed stage after {current} is {expected_next}."
    if next_status in {"Picking", "Packing"}:
        fs = fulfillment_status(order_id)
        if fs.startswith("Blocked"):
            return False, f"Order cannot move to {next_status}: {fs}."
    if next_status == "Packing" and not has_pick_verification(order_id):
        return False, "Picking must be verified by SKU before the order can move to Packing."
    return True, "OK"


def update_order_status(order_id: str, next_status: str) -> tuple[bool, str]:
    info = order_info(order_id)
    if info is None:
        return False, "Order not found."
    ok, message = can_move(order_id, next_status)
    if not ok:
        return False, message

    old_status = info["status"]
    tracking_number = info["tracking_number"] or f"TRK{abs(hash(order_id)) % 90000000 + 10000000}"
    with get_connection() as conn:
        conn.execute(
            "UPDATE orders SET status = ?, tracking_number = CASE WHEN ? = 'Shipped' THEN COALESCE(tracking_number, ?) ELSE tracking_number END WHERE order_id = ?",
            (next_status, next_status, tracking_number, order_id),
        )
        if next_status in {"Packing", "Staged"}:
            existing = conn.execute("SELECT 1 FROM shipments WHERE order_id = ?", (order_id,)).fetchone()
            if not existing:
                pickup_time = conn.execute("SELECT datetime('now', '+60 minutes')").fetchone()[0]
                conn.execute(
                    "INSERT INTO shipments(order_id, courier, pickup_time, staging_location, status) VALUES (?, ?, ?, ?, ?)",
                    (order_id, info["courier"], pickup_time, f"STAGE-A-{int(order_id[-2:]) % 20 + 1:02d}", "Awaiting Pickup"),
                )
        if next_status == "Shipped":
            conn.execute("UPDATE shipments SET status = 'Picked Up' WHERE order_id = ?", (order_id,))
        conn.commit()
    log_activity(order_id, f"Status changed from {old_status} to {next_status}", old_status, next_status)
    return True, f"Order moved to {next_status}."

def complete_transfer(transfer_id: int) -> tuple[bool, str]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM transfers WHERE transfer_id = ?", (transfer_id,)).fetchone()
        if not row:
            return False, "Transfer not found."
        if row["status"] != "Pending":
            return False, "This transfer is not pending."
        source = conn.execute(
            "SELECT quantity, reserved_quantity FROM inventory WHERE warehouse_id = ? AND sku = ?",
            (row["from_warehouse"], row["sku"]),
        ).fetchone()
        target = conn.execute(
            "SELECT quantity, reserved_quantity FROM inventory WHERE warehouse_id = ? AND sku = ?",
            (row["to_warehouse"], row["sku"]),
        ).fetchone()
        if not source or source["quantity"] - source["reserved_quantity"] < row["quantity"]:
            return False, "Not enough available stock in the source warehouse."
        if not target:
            return False, "Target warehouse SKU record not found."
        conn.execute(
            "UPDATE inventory SET quantity = quantity - ? WHERE warehouse_id = ? AND sku = ?",
            (row["quantity"], row["from_warehouse"], row["sku"]),
        )
        conn.execute(
            "UPDATE inventory SET quantity = quantity + ? WHERE warehouse_id = ? AND sku = ?",
            (row["quantity"], row["to_warehouse"], row["sku"]),
        )
        completed_at = datetime.now().replace(microsecond=0).isoformat(sep=" ")
        conn.execute(
            "UPDATE transfers SET status = 'Completed', completed_at = ? WHERE transfer_id = ?",
            (completed_at, transfer_id),
        )
        conn.commit()
    log_activity(row["order_id"], f"Warehouse transfer {transfer_id} completed", None, None)
    return True, "Transfer completed and inventory updated."


def verify_and_pick(order_id: str, entered_values: dict[str, str]) -> tuple[bool, str]:
    inv = order_inventory(order_id)
    if inv.empty:
        return False, "This order has no items."
    for _, row in inv.iterrows():
        entered = entered_values.get(row["SKU"], "").strip().upper()
        if entered != row["SKU"].upper():
            return False, f"Verification failed for {row['SKU']}. Expected {row['SKU']}, entered {entered or '[blank]'}."
        if row["Availability"] != "Available":
            return False, f"{row['SKU']} is not available in Main Warehouse yet."
    info = order_info(order_id)
    if info is None or info["status"] != "Picking":
        return False, "Order must be in Picking status before it can be verified."

    with get_connection() as conn:
        conn.execute("UPDATE orders SET status = 'Packing' WHERE order_id = ?", (order_id,))
        existing = conn.execute("SELECT 1 FROM shipments WHERE order_id = ?", (order_id,)).fetchone()
        if not existing:
            pickup_time = conn.execute("SELECT datetime('now', '+60 minutes')").fetchone()[0]
            conn.execute(
                "INSERT INTO shipments(order_id, courier, pickup_time, staging_location, status) VALUES (?, ?, ?, ?, ?)",
                (order_id, info["courier"], pickup_time, f"STAGE-A-{int(order_id[-2:]) % 20 + 1:02d}", "Awaiting Pickup"),
            )
        conn.commit()
    log_activity(order_id, "Picking verification passed", "Picking", "Packing")
    log_activity(order_id, "Status changed from Picking to Packing", "Picking", "Packing")
    return True, "All SKUs verified. Order moved to Packing."

def create_issue(order_id: str | None, issue_type: str, description: str, priority: str, assigned_to: str) -> None:
    execute(
        """INSERT INTO issues(order_id, issue_type, description, priority, status, assigned_to, created_at)
           VALUES (?, ?, ?, ?, 'Open', ?, ?)""",
        (order_id or None, issue_type, description, priority, assigned_to, datetime.now().replace(microsecond=0).isoformat(sep=" ")),
    )


def resolve_issue(issue_id: int) -> None:
    execute(
        "UPDATE issues SET status = 'Resolved', resolved_at = ? WHERE issue_id = ?",
        (datetime.now().replace(microsecond=0).isoformat(sep=" "), issue_id),
    )


def dashboard() -> None:
    st.title("📦 Fulfillment Hub")
    st.caption("A simple operational control center for XYZ's order fulfillment workflow")

    today = datetime.now().date().isoformat()
    total = scalar("SELECT COUNT(*) FROM orders")
    priority_count = scalar("SELECT COUNT(*) FROM orders WHERE priority = 'High' AND status != 'Shipped'")
    shipped = scalar("SELECT COUNT(*) FROM orders WHERE status = 'Shipped'")
    open_issues = scalar("SELECT COUNT(*) FROM issues WHERE status != 'Resolved'")
    pending_transfers = scalar("SELECT COUNT(*) FROM transfers WHERE status = 'Pending'")
    overdue = scalar(
        "SELECT COUNT(*) FROM orders WHERE status != 'Shipped' AND deadline < ?",
        (datetime.now().isoformat(sep=" "),),
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Orders", total)
    c2.metric("Priority", priority_count)
    c3.metric("Shipped", shipped)
    c4.metric("Overdue", overdue)
    c5.metric("Open Issues", open_issues)
    c6.metric("Pending Transfers", pending_transfers)

    st.divider()

    actions = []
    if overdue:
        actions.append(f"🔴 {overdue} overdue order(s) need attention")
    if priority_count:
        actions.append(f"🟠 {priority_count} priority order(s) are still open")
    if pending_transfers:
        actions.append(f"🟡 {pending_transfers} inventory transfer(s) are pending")
    if open_issues:
        actions.append(f"⚠️ {open_issues} operational issue(s) are open/in progress")

    st.subheader("Action Required")
    if actions:
        for action in actions:
            st.warning(action)
    else:
        st.success("No outstanding operational exceptions.")

    st.divider()
    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("🚨 Priority Queue")
        priority_df = query_df(
            """SELECT order_id AS 'Order ID', customer_name AS Customer, status AS Status,
                      deadline AS Deadline, courier AS Courier
               FROM orders
               WHERE priority = 'High' AND status != 'Shipped'
               ORDER BY deadline ASC LIMIT 12"""
        )
        if priority_df.empty:
            st.info("No outstanding priority orders.")
        else:
            priority_df["Deadline"] = pd.to_datetime(priority_df["Deadline"]).dt.strftime("%d %b %I:%M %p")
            st.dataframe(priority_df, use_container_width=True, hide_index=True)
    with right:
        st.subheader("📊 Order Status")
        status_df = query_df("SELECT status AS Status, COUNT(*) AS Orders FROM orders GROUP BY status ORDER BY Orders DESC")
        st.bar_chart(status_df.set_index("Status"))

    st.divider()
    left, right = st.columns(2)
    with left:
        st.subheader("⚠️ Inventory Exceptions")
        inv_df = query_df(
            """SELECT oi.order_id AS 'Order ID', oi.sku AS SKU, oi.quantity AS Required,
                      COALESCE(m.quantity - m.reserved_quantity, 0) AS 'Main Available',
                      COALESCE(s.quantity - s.reserved_quantity, 0) AS 'Secondary Available'
               FROM order_items oi
               JOIN orders o ON o.order_id = oi.order_id
               LEFT JOIN inventory m ON m.sku = oi.sku AND m.warehouse_id = 'WH01'
               LEFT JOIN inventory s ON s.sku = oi.sku AND s.warehouse_id = 'WH02'
               WHERE o.status != 'Shipped'
                 AND COALESCE(m.quantity - m.reserved_quantity, 0) < oi.quantity
               ORDER BY CASE WHEN o.priority='High' THEN 0 ELSE 1 END, oi.order_id LIMIT 12"""
        )
        if inv_df.empty:
            st.success("No current inventory exceptions.")
        else:
            inv_df["Action"] = inv_df.apply(
                lambda r: "Transfer Required" if r["Main Available"] + r["Secondary Available"] >= r["Required"] else "Out of Stock",
                axis=1,
            )
            st.dataframe(inv_df, use_container_width=True, hide_index=True)
    with right:
        st.subheader("🚚 Upcoming / Missed Pickups")
        shipment_df = query_df(
            """SELECT order_id AS 'Order ID', courier AS Courier,
                      pickup_time AS 'Pickup Time', staging_location AS 'Stage', status AS Status
               FROM shipments
               WHERE status IN ('Awaiting Pickup', 'Missed Pickup')
               ORDER BY pickup_time ASC LIMIT 12"""
        )
        if shipment_df.empty:
            st.info("No pickup exceptions.")
        else:
            shipment_df["Pickup Time"] = pd.to_datetime(shipment_df["Pickup Time"]).dt.strftime("%d %b %I:%M %p")
            st.dataframe(shipment_df, use_container_width=True, hide_index=True)


def orders_page() -> None:
    st.title("📦 Orders")
    st.caption("Search and prioritize the fulfillment queue")

    c1, c2, c3, c4 = st.columns([1.8, 1, 1, 1])
    search = c1.text_input("Search Order / Customer", placeholder="ORD-1001 or Rahul")
    priority_filter = c2.selectbox("Priority", ["All", "High", "Normal"])
    status_filter = c3.selectbox("Status", ["All"] + ["Received", "Processing", "Picking", "Packing", "Staged", "Shipped"])
    urgency_filter = c4.selectbox("Urgency", ["All", "Overdue", "Priority", "Normal", "Completed"])

    sql = """SELECT order_id AS 'Order ID', customer_name AS Customer, priority AS Priority,
                     status AS Status, deadline AS Deadline, courier AS Courier
              FROM orders WHERE 1=1"""
    params: list[str] = []
    if search:
        sql += " AND (order_id LIKE ? OR customer_name LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term])
    if priority_filter != "All":
        sql += " AND priority = ?"
        params.append(priority_filter)
    if status_filter != "All":
        sql += " AND status = ?"
        params.append(status_filter)
    sql += " ORDER BY CASE WHEN priority = 'High' THEN 0 ELSE 1 END, deadline ASC"
    df = query_df(sql, tuple(params))
    if not df.empty:
        df["Deadline"] = pd.to_datetime(df["Deadline"])
        df.insert(4, "Urgency", [urgency(p, d.isoformat(), s) for p, d, s in zip(df["Priority"], df["Deadline"], df["Status"])])
        df["Deadline"] = df["Deadline"].dt.strftime("%d %b %I:%M %p")
        if urgency_filter != "All":
            df = df[df["Urgency"] == urgency_filter]

    st.write(f"Showing **{len(df)}** order(s)")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    order_ids = query_df("SELECT order_id FROM orders ORDER BY order_id")
    selected = st.selectbox("Open an order", order_ids["order_id"].tolist())
    if st.button("Open Order Details", type="primary"):
        st.session_state["selected_order"] = selected
        st.session_state["page"] = "Order Details"
        st.rerun()


def order_details_page() -> None:
    st.title("🔎 Order Details")
    ids = query_df("SELECT order_id FROM orders ORDER BY order_id")["order_id"].tolist()
    default = st.session_state.get("selected_order", ids[0])
    default_index = ids.index(default) if default in ids else 0
    selected = st.selectbox("Order", ids, index=default_index)
    st.session_state["selected_order"] = selected

    info = order_info(selected)
    if info is None:
        st.error("Order not found.")
        return

    current_urgency = urgency(info["priority"], info["deadline"], info["status"])
    fs = fulfillment_status(selected)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customer", info["customer_name"])
    c2.metric("Priority", info["priority"])
    c3.metric("Status", info["status"])
    c4.metric("Urgency", current_urgency)

    if current_urgency == "Overdue":
        st.error(f"Deadline missed: {fmt_dt(info['deadline'])}")
    elif current_urgency == "Priority":
        st.warning(f"Priority order — deadline {fmt_dt(info['deadline'])}")
    else:
        st.info(f"Deadline: {fmt_dt(info['deadline'])}")

    st.subheader("Fulfillment Journey")
    stages = ["Received", "Processing", "Picking", "Packing", "Staged", "Shipped"]
    labels = []
    idx = status_index(info["status"])
    for i, stage in enumerate(stages):
        if i < idx:
            labels.append(f"✅ {stage}")
        elif i == idx:
            labels.append(f"➡️ {stage}")
        else:
            labels.append(f"⬜ {stage}")
    st.write("  →  ".join(labels))

    left, right = st.columns([1.3, 1])
    with left:
        st.subheader("Items & Inventory")
        inv = order_inventory(selected)
        st.dataframe(inv, use_container_width=True, hide_index=True)
        if fs.startswith("Blocked"):
            if "Transfer" in fs:
                st.warning("Stock exists in Secondary Warehouse. Create or complete a transfer before picking.")
            else:
                st.error("This order is blocked by insufficient stock across both warehouses.")
        else:
            st.success("All required items are available in Main Warehouse.")

    with right:
        st.subheader("Courier")
        st.write(f"**Courier:** {info['courier']}")
        st.write(f"**Tracking:** {info['tracking_number'] or 'Not assigned yet'}")
        shipment = query_df("SELECT * FROM shipments WHERE order_id = ?", (selected,))
        if shipment.empty:
            st.info("Shipment record will be created during packing/staging.")
        else:
            row = shipment.iloc[0]
            st.write(f"**Pickup:** {fmt_dt(row['pickup_time'])}")
            st.write(f"**Stage:** {row['staging_location'] or 'Not assigned'}")
            st.write(f"**Pickup status:** {row['status']}")

        st.subheader("Actions")
        current = info["status"]
        next_map = {"Received": "Processing", "Processing": "Picking", "Picking": "Packing", "Packing": "Staged", "Staged": "Shipped"}
        next_status = next_map.get(current)
        if next_status:
            disabled = False
            if next_status in {"Picking", "Packing"} and fs.startswith("Blocked"):
                disabled = True
            if st.button(f"Move to {next_status}", type="primary", disabled=disabled):
                ok, msg = update_order_status(selected, next_status)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.success("Order is fully shipped.")

    if current == "Picking":
        st.divider()
        st.subheader("🎯 Picking Verification")
        inv = order_inventory(selected)
        with st.form("pick_verification"):
            st.caption("Enter the SKU exactly as shown. This is a demo substitute for a barcode scan.")
            entered = {}
            for _, row in inv.iterrows():
                entered[row["SKU"]] = st.text_input(
                    f"Verify {row['Product']} — {row['Variant']} (expected {row['SKU']})",
                    key=f"verify_{selected}_{row['SKU']}",
                )
            submitted = st.form_submit_button("Verify & Complete Picking", type="primary")
        if submitted:
            ok, msg = verify_and_pick(selected, entered)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.divider()
    st.subheader("⚠️ Issues")
    issues = query_df(
        """SELECT issue_id AS 'Issue ID', issue_type AS Type, priority AS Priority,
                  status AS Status, assigned_to AS 'Assigned To', description AS Description,
                  created_at AS Created
           FROM issues WHERE order_id = ? ORDER BY issue_id DESC""",
        (selected,),
    )
    if issues.empty:
        st.success("No issues recorded for this order.")
    else:
        issues["Created"] = issues["Created"].map(fmt_dt)
        st.dataframe(issues, use_container_width=True, hide_index=True)

    st.subheader("Activity History")
    activity = query_df(
        """SELECT action AS Action, old_status AS 'From', new_status AS 'To', user AS User, timestamp AS Time
           FROM activity_log WHERE order_id = ? ORDER BY timestamp DESC""",
        (selected,),
    )
    if activity.empty:
        st.info("No activity history recorded yet.")
    else:
        activity["Time"] = activity["Time"].map(fmt_dt)
        st.dataframe(activity, use_container_width=True, hide_index=True)


def inventory_page() -> None:
    st.title("📦 Inventory")
    st.caption("See what can be picked now and what needs a warehouse transfer")
    df = query_df(
        """SELECT p.sku AS SKU, p.product_name AS Product, p.variant AS Variant,
                  MAX(CASE WHEN i.warehouse_id = 'WH01' THEN i.quantity ELSE 0 END) AS 'Main Qty',
                  MAX(CASE WHEN i.warehouse_id = 'WH01' THEN i.reserved_quantity ELSE 0 END) AS 'Main Reserved',
                  MAX(CASE WHEN i.warehouse_id = 'WH02' THEN i.quantity ELSE 0 END) AS 'Secondary Qty',
                  MAX(CASE WHEN i.warehouse_id = 'WH02' THEN i.reserved_quantity ELSE 0 END) AS 'Secondary Reserved'
           FROM products p LEFT JOIN inventory i ON p.sku = i.sku
           GROUP BY p.sku, p.product_name, p.variant ORDER BY p.sku"""
    )
    df["Main Available"] = df["Main Qty"] - df["Main Reserved"]
    df["Secondary Available"] = df["Secondary Qty"] - df["Secondary Reserved"]
    df["Action"] = df.apply(
        lambda r: "OK" if r["Main Available"] > 0 else ("Transfer from Secondary" if r["Secondary Available"] > 0 else "Out of Stock"),
        axis=1,
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Stock Health")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pickable SKUs", int((df["Main Available"] > 0).sum()))
    c2.metric("Transfer Candidates", int(((df["Main Available"] <= 0) & (df["Secondary Available"] > 0)).sum()))
    c3.metric("Out of Stock SKUs", int(((df["Main Available"] <= 0) & (df["Secondary Available"] <= 0)).sum()))


def transfers_page() -> None:
    st.title("🔄 Warehouse Transfers")
    st.caption("Move stock from Secondary Warehouse to Main Warehouse before picking")
    pending = query_df(
        """SELECT transfer_id AS 'Transfer ID', order_id AS 'Order ID', sku AS SKU, quantity AS Quantity,
                  from_warehouse AS From_WH, to_warehouse AS To_WH, status AS Status, created_at AS Created
           FROM transfers WHERE status = 'Pending' ORDER BY created_at ASC"""
    )
    if pending.empty:
        st.success("No pending transfers.")
    else:
        st.dataframe(pending, use_container_width=True, hide_index=True)
        selected = st.selectbox("Select a pending transfer", pending["Transfer ID"].tolist())
        if st.button("✅ Complete Transfer", type="primary"):
            ok, msg = complete_transfer(int(selected))
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.divider()
    st.subheader("Transfer History")
    history = query_df(
        """SELECT transfer_id AS 'Transfer ID', order_id AS 'Order ID', sku AS SKU, quantity AS Quantity,
                  from_warehouse AS From_WH, to_warehouse AS To_WH, status AS Status, created_at AS Created,
                  completed_at AS Completed
           FROM transfers ORDER BY transfer_id DESC"""
    )
    st.dataframe(history, use_container_width=True, hide_index=True)


def fulfillment_page() -> None:
    st.title("🎯 Fulfillment Queue")
    st.caption("Move work through picking, packing and staging in the intended order")
    stages = ["Picking", "Packing", "Staged"]
    cols = st.columns(3)
    for col, stage in zip(cols, stages):
        with col:
            st.subheader(stage)
            df = query_df(
                """SELECT order_id AS 'Order ID', priority AS Priority, customer_name AS Customer,
                          courier AS Courier, deadline AS Deadline
                   FROM orders WHERE status = ? ORDER BY CASE WHEN priority='High' THEN 0 ELSE 1 END, deadline ASC LIMIT 12""",
                (stage,),
            )
            if df.empty:
                st.info("No orders here.")
            else:
                df["Deadline"] = pd.to_datetime(df["Deadline"]).dt.strftime("%d %b %I:%M %p")
                st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Open an Order")
    order_ids = query_df("SELECT order_id FROM orders ORDER BY order_id")["order_id"].tolist()
    selected = st.selectbox("Order", order_ids)
    if st.button("Open Selected Order", type="secondary"):
        st.session_state["selected_order"] = selected
        st.session_state["page"] = "Order Details"
        st.rerun()


def shipments_page() -> None:
    st.title("🚚 Shipments & Staging")
    st.caption("Know where every packed box is and what the courier is expected to collect")
    df = query_df(
        """SELECT s.order_id AS 'Order ID', o.priority AS Priority, s.courier AS Courier,
                  s.pickup_time AS 'Pickup Time', s.staging_location AS 'Stage Location', s.status AS Status
           FROM shipments s JOIN orders o ON o.order_id = s.order_id
           ORDER BY CASE WHEN s.status='Missed Pickup' THEN 0 ELSE 1 END, s.pickup_time ASC"""
    )
    if not df.empty:
        df["Pickup Time"] = pd.to_datetime(df["Pickup Time"]).dt.strftime("%d %b %I:%M %p")
    st.dataframe(df, use_container_width=True, hide_index=True)


def issues_page() -> None:
    st.title("⚠️ Issues")
    st.caption("Turn informal problems into visible, trackable work")
    status = st.selectbox("Status", ["All", "Open", "In Progress", "Resolved"])
    sql = """SELECT issue_id AS 'Issue ID', order_id AS 'Order ID', issue_type AS Type,
                     priority AS Priority, status AS Status, assigned_to AS 'Assigned To',
                     description AS Description, created_at AS Created
              FROM issues"""
    params: tuple = ()
    if status != "All":
        sql += " WHERE status = ?"
        params = (status,)
    sql += " ORDER BY CASE WHEN priority='High' THEN 0 WHEN priority='Medium' THEN 1 ELSE 2 END, created_at DESC"
    df = query_df(sql, params)
    if not df.empty:
        df["Created"] = df["Created"].map(fmt_dt)
    st.dataframe(df, use_container_width=True, hide_index=True)

    open_df = query_df("SELECT issue_id FROM issues WHERE status != 'Resolved' ORDER BY issue_id DESC")
    if not open_df.empty:
        st.divider()
        selected = st.selectbox("Select issue to resolve", open_df["issue_id"].tolist())
        if st.button("✅ Resolve Issue", type="primary"):
            resolve_issue(int(selected))
            st.success("Issue marked as resolved.")
            st.rerun()

    st.divider()
    st.subheader("Create Issue")
    order_ids = query_df("SELECT order_id FROM orders ORDER BY order_id")["order_id"].tolist()
    with st.form("create_issue"):
        order_id = st.selectbox("Order (optional)", ["General"] + order_ids)
        issue_type = st.selectbox("Issue Type", ["Inventory", "Wrong SKU", "Staging", "Courier Pickup", "Other"])
        priority = st.selectbox("Priority", ["High", "Medium", "Low"])
        assigned_to = st.selectbox("Assigned To", ["Warehouse Team", "Picking Team", "Office Team"])
        description = st.text_area("Description")
        submitted = st.form_submit_button("Create Issue")
    if submitted:
        if not description.strip():
            st.error("Please enter a description.")
        else:
            create_issue(None if order_id == "General" else order_id, issue_type, description.strip(), priority, assigned_to)
            st.success("Issue created.")
            st.rerun()


ensure_database()

# Small amount of CSS to keep the interface compact and operational.
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
    [data-testid="stMetricValue"] {font-size: 1.55rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.title("📦 Fulfillment Hub")
st.sidebar.caption("XYZ Operations")

pages = ["Dashboard", "Orders", "Order Details", "Inventory", "Transfers", "Fulfillment", "Shipments", "Issues"]
current_page = st.session_state.get("page", "Dashboard")
if current_page not in pages:
    current_page = "Dashboard"
page = st.sidebar.radio("Navigate", pages, index=pages.index(current_page))
st.session_state["page"] = page

st.sidebar.divider()
st.sidebar.write("**Workflow**")
st.sidebar.caption("Received → Processing → Picking → Packing → Staged → Shipped")
st.sidebar.divider()
st.sidebar.caption("Demo dataset: 250 orders • 2 warehouses")

if page == "Dashboard":
    dashboard()
elif page == "Orders":
    orders_page()
elif page == "Order Details":
    order_details_page()
elif page == "Inventory":
    inventory_page()
elif page == "Transfers":
    transfers_page()
elif page == "Fulfillment":
    fulfillment_page()
elif page == "Shipments":
    shipments_page()
elif page == "Issues":
    issues_page()
