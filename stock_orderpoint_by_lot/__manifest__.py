# Copyright 2025 Akretion France (https://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
{
    "name": "Stock Orderpoint by lot",
    "summary": "Replenish only some lots",
    "version": "18.0.1.1.0",
    "license": "LGPL-3",
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
    "author": "Akretion, Odoo Community Association (OCA)",
    "category": "Warehouse",
    "depends": ["purchase_lot", "stock_restrict_lot"],
    "data": [
        "security/ir.model.access.csv",
        "security/stock_quantity_by_lot_security.xml",
        "views/product_template.xml",
        "views/stock_orderpoint.xml",
        "views/stock_quantity_by_lot.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_orderpoint_by_lot/static/src/stock_forecasted.*",
        ],
        "web.assets_backend_lazy": [
            "stock_orderpoint_by_lot/static/src/forecasted_graph.js",
        ],
    },
    "installable": True,
}
