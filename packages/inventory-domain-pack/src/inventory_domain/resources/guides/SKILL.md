# Read-only Inventory Guide

Open warehouse-a with inventory_catalog_open, then use the returned context_ref
unchanged with inventory_asset_list, inventory_asset_get, or
inventory_stock_summary.

Inventory results and evidence are valid only for the current run. This domain
does not publish any mutation capability.
