# Copyright 2025 Akretion France (https://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>
from odoo import Command, _, models
from odoo.exceptions import UserError


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    def action_replenish(self, force_to_max=False):
        orderpoint_multiple_supplier_no_choice = self.filtered(
            lambda r: len(r.product_id.seller_ids) > 1 and not r.supplier_id
        )
        orderpoint_single_supplier = self - orderpoint_multiple_supplier_no_choice

        res = super(
            StockWarehouseOrderpoint, orderpoint_single_supplier
        ).action_replenish(force_to_max)

        if len(orderpoint_multiple_supplier_no_choice.mapped("warehouse_id")) > 1:
            raise UserError("Cannot ressuply with supplier into multiple warehouses")

        if len(orderpoint_multiple_supplier_no_choice) == 0:
            return res

        wizard = self.env["multi.supplier.replenish"].create(
            [
                {
                    "product_ids_lot_ids": [
                        (o.product_id.id, o.lot_id.id)
                        for o in orderpoint_multiple_supplier_no_choice
                    ],
                    "warehouse_id": self.warehouse_id.id,
                    "product_replenish_ids": [],
                    "company_id": self.env.company.id,
                },
            ]
        )

        return wizard.action_multi_supplier_replenish()
