# Data Dictionary

## products

| Column | Description |
|---|---|
| product_id | Internal product identifier |
| sku | Unique stock keeping unit |
| product_name | Product name |
| category | Product category |
| variant | Variant details such as color/size |

## warehouses

| Column | Description |
|---|---|
| warehouse_id | Warehouse identifier |
| warehouse_name | Display name |
| location | Demo location label |
| is_primary | 1 for Main Warehouse, 0 otherwise |

## inventory

| Column | Description |
|---|---|
| inventory_id | Row identifier |
| warehouse_id | Warehouse holding stock |
| sku | Product SKU |
| quantity | Physical quantity recorded |
| reserved_quantity | Quantity already reserved |

**Available = quantity - reserved_quantity**

## orders

| Column | Description |
|---|---|
| order_id | Order identifier |
| order_date | Order creation timestamp |
| customer_name | Demo customer name |
| priority | High or Normal |
| deadline | Demo fulfillment deadline |
| status | Received, Processing, Picking, Packing, Staged, Shipped |
| courier | Selected demo courier |
| tracking_number | Demo tracking reference when shipped |

## order_items

Connects orders to one or more SKUs and required quantities.

## transfers

Records inventory movement from Secondary to Main Warehouse.

## shipments

Records courier, pickup time, staging location and pickup status.

## issues

Tracks operational exceptions such as inventory, wrong SKU, staging and courier pickup problems.

## activity_log

Records order actions and status changes for traceability.
