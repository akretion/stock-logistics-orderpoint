# Copyright 2025 Akretion France (https://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
{
    "name": "Stock Orderpoint by lot",
    "summary": "Replenish only some lots",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
    "author": "Akretion, Odoo Community Association (OCA)",
    "category": "Warehouse",
    "depends": ["purchase_lot", "stock_restrict_lot"],
    "data": [
        "views/stock_orderpoint.xml",
        "views/product_template.xml",
    ],
    "installable": True,
}
