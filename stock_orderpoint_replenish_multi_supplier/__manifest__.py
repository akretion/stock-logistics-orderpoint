# Copyright 2023 Michael Tietz (MT Software) <mtietz@mt-software.de>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Stock Location Replenish Multi supplier",
    "author": "Akretion, Odoo Community Association (OCA)",
    "summary": "Ask supplier id on orderpoint confirmation when the choice has not been made",
    "version": "18.0.1.0.0",
    "data": [
        "wizard/multi_supplier_replenish.xml",
        "views/product_views.xml",
        "views/product_replenish_views.xml",
        "security/ir.model.access.csv",
    ],
    "depends": [
        "stock",
        "purchase_stock",
        "stock_orderpoint_by_lot",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_orderpoint_replenish_multi_supplier/static/src/**/*.js",
            "stock_orderpoint_replenish_multi_supplier/static/src/**/*.xml",
        ],
    },
    "license": "AGPL-3",
    "maintainers": ["franzpoize"],
}
