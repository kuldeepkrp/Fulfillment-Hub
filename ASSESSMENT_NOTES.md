# Assessment Notes

## 1. Problem understanding

XYZ's core issue is not simply "too many orders". The operational weakness is that fulfillment work is coordinated across spreadsheets, shared documents, and informal communication. This makes state, exceptions, and deadlines hard to see and act upon.

## 2. Prioritization

I prioritized the problems that can directly stop or delay shipment:

1. **Order visibility and priority handling** — operators need to know what requires attention first.
2. **Inventory exceptions** — an order should not reach picking if required stock is unavailable in the Main Warehouse.
3. **Warehouse transfers** — Secondary Warehouse stock needs to be moved before it can be picked.
4. **Picking verification** — product/variant errors should be caught before packing.
5. **Exception tracking and staging/shipment visibility** — problems should become visible work instead of informal reminders.

## 3. Product principle

The application is deliberately simple because the warehouse team is experienced but not very comfortable with technology. The system should tell a worker **what needs attention and what the next action is**, rather than expose complex ERP-style screens.

## 4. Business rules

- Orders follow a controlled stage sequence.
- Priority orders are surfaced before normal orders.
- Overdue orders are visible as exceptions.
- An order can be picked only when required SKUs are available in Main Warehouse.
- If stock is missing in Main but exists in Secondary, a transfer is required.
- Picking verification requires the exact expected SKU for each line.
- Issues can be assigned, tracked, and resolved.
- Order status changes are recorded in an activity log.

## 5. Demo assumptions

The assessment permits dummy operational data. The included database therefore uses 250 sample orders, two warehouses, three sample couriers, product variants, shipment records, transfer records, and operational issues. These figures are demo assumptions rather than claims about XYZ's actual internal data.
