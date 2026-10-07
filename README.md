# Fulfillment Hub

Take-home project solution for **XYZ's e-commerce fulfillment operations**.

## Problem

XYZ currently manages fulfillment through spreadsheets and shared folders. The assessment highlights several operational problems: weak order-status visibility, unnoticed delays, priority orders missing deadlines, inventory records that do not match available stock, wrong product/variant shipments, misplaced packed boxes or missed courier pickups, and informal issue handling.

## Solution

Fulfillment Hub is a lightweight operational control center built around the fulfillment workflow:

**Received → Processing → Picking → Packing → Staged → Shipped**

The app focuses on the highest-value operational controls:

- Order visibility and priority queue
- Deadline / overdue visibility
- Inventory availability in Main vs Secondary Warehouse
- Warehouse transfer workflow
- Picking SKU verification
- Packing / staging / shipment visibility
- Operational issue tracking
- Activity history for order changes

## Tech stack

- Python 3.10+
- Streamlit 1.65.0
- SQLite
- Pandas 2.3.3

## Included files

```text
Fulfillment-Hub/
├── app.py
├── seed_database.py
├── fulfillment_hub.db
├── requirements.txt
├── README.md
├── AI_USAGE.md
├── ASSESSMENT_NOTES.md
├── run_app.bat
├── setup_windows.bat
├── .gitignore
├── .streamlit/
│   └── config.toml
├── data/
│   ├── products.csv
│   ├── warehouses.csv
│   ├── inventory.csv
│   ├── orders.csv
│   ├── order_items.csv
│   ├── transfers.csv
│   ├── shipments.csv
│   ├── issues.csv
│   └── activity_log.csv
└── docs/
    └── DATA_DICTIONARY.md
```

## Run locally on Windows

### Option A — easiest

Double-click `setup_windows.bat` once. It creates a virtual environment and installs dependencies.

Then double-click `run_app.bat`.

### Option B — terminal

Open Command Prompt in the project folder and run:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
streamlit run app.py
```

Then open `http://localhost:8501`.

## Reset the demo database

To regenerate the complete sample dataset from scratch:

```bat
python seed_database.py
```

This recreates the SQLite database and refreshes the CSV sample-data exports.

## Demo scenario for the video

Use **ORD-1001**, **ORD-1002**, or **ORD-1003** to demonstrate:

1. Open the priority order.
2. Show that SHOE-BLK-42 is unavailable in Main Warehouse.
3. Open **Transfers** and show the pending transfer from WH02 to WH01.
4. Complete the transfer.
5. Return to the order and show inventory is now available.
6. Move the order into Picking.
7. In Picking Verification, enter the exact expected SKU.
8. Complete picking and move the order through Packing → Staged → Shipped.
9. Open **Issues** to show how operational exceptions are tracked and resolved.

## Deployment

See `docs/DEPLOY_STREAMLIT.md` for the step-by-step Community Cloud deployment flow. Keep `app.py` and `requirements.txt` in the repository root. The included SQLite demo database is also part of the repository so the hosted demo has sample data available immediately.

Streamlit Community Cloud deploys from GitHub and can use the repository's `requirements.txt` for dependencies. The current Streamlit documentation recommends keeping the dependency file in the repository root or alongside the entrypoint and running the app from the repository root so file paths behave consistently locally and in the cloud.
