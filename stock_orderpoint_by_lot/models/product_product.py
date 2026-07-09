# Copyright 2025 Akretion France (https://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>

from collections import defaultdict

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_quantity_in_progress_by_lot(
        self, location_ids=False, warehouse_ids=False, lot_ids=False
    ):
        if not location_ids:
            location_ids = []
        if not warehouse_ids:
            warehouse_ids = []
        if not lot_ids:
            lot_ids = []

        qty_by_product_location, qty_by_product_wh = (
            defaultdict(float),
            defaultdict(float),
        )

        domain = self._get_lines_domain(location_ids, warehouse_ids)
        groups = (
            self.env["purchase.order.line"]
            .sudo()
            ._read_group(
                domain,
                [
                    "order_id",
                    "product_id",
                    "product_uom",
                    "orderpoint_id",
                    "location_final_id",
                    "lot_id",
                ],
                ["product_qty:sum"],
            )
        )
        for (
            order,
            product,
            uom,
            orderpoint,
            location_final,
            lot_id,
            product_qty_sum,
        ) in groups:
            if orderpoint:
                location = orderpoint.location_id
            elif location_final:
                location = location_final
            else:
                location = order.picking_type_id.default_location_dest_id
            product_qty = uom._compute_quantity(
                product_qty_sum, product.uom_id, round=False
            )
            qty_by_product_location[(product.id, location.id, lot_id.id)] += product_qty
            qty_by_product_wh[(product.id, location.warehouse_id.id, lot_id.id)] += (
                product_qty
            )
        return qty_by_product_location, qty_by_product_wh
