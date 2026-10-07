# 5-Minute Video Walkthrough Script

## 0:00–0:40 — Problem

"I understood XYZ's main challenge as a fulfillment visibility and execution problem. Orders are currently coordinated through spreadsheets and shared folders, which makes status, deadlines, inventory exceptions and operational issues difficult to track."

## 0:40–1:05 — Prioritization

"I focused on the controls that most directly affect on-time shipment: order visibility, priority orders, inventory availability, warehouse transfers, picking verification, and exception tracking."

## 1:05–3:55 — Product demo

1. Dashboard: show KPIs and Action Required.
2. Priority queue: open ORD-1001.
3. Order Details: show the fulfillment journey and inventory exception.
4. Transfers: complete the pending SHOE-BLK-42 transfer.
5. Return to the order and show Main Warehouse availability.
6. Move into Picking.
7. Verify the exact expected SKU and move to Packing.
8. Move through Staged and Shipped.
9. Open Issues and resolve one issue.

## 3:55–4:30 — Design decisions

"I intentionally kept the warehouse interface simple. The system highlights what needs attention and the next allowed action instead of exposing a complex ERP screen. The transfer and SKU-verification controls are examples of business rules I added to prevent predictable fulfillment failures."

## 4:30–5:00 — AI use

"I used AI to help with requirement breakdown, schema design, sample data, coding and debugging. I still reviewed and changed the suggestions. In particular, I chose a simpler Streamlit plus SQLite architecture instead of a more complex service architecture, and I used SKU verification instead of pretending we had a real barcode integration."
