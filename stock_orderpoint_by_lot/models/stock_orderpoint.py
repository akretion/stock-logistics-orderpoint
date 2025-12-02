# Copyright 2025 Akretion France (https://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>

from collections import defaultdict

from dateutil import relativedelta

from odoo import fields, models
from odoo.osv import expression
from odoo.tools import float_compare


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    replenish_by_lot = fields.Boolean(related="product_id.replenish_by_lot")

    def _prepare_procurement_values(self, date=False, group=False):
        # add a replenish_by_lots in values
        # like { lot1: qty1, lot5: qty2}
        res = super()._prepare_procurement_values(date, group)
        if not self.replenish_by_lot:
            # exit early
            return res

        qty_by_lot = self._get_qty_to_order_by_lot()
        lots = {}
        # extract by location
        for (prod, loc, lot), qty in qty_by_lot.items():
            if prod == self.product_id.id and loc == self.location_id.id:
                lots[lot] = qty

        res["replenish_by_lots"] = lots
        return res

    def _get_qty_to_order_by_lot(self):  # noqa: C901
        # copied from stock/models/stock_orderpoint.py
        # _get_orderpoint_action
        # added the ability to manage lots
        # the original function is quite long and can't be
        # overriden
        # differences are marked with #diff comment
        # return (product_id, location_id, lot_id) : qty

        def is_parent_path_in(resupply_loc, path_dict, record_loc):
            return record_loc and resupply_loc.parent_path in path_dict.get(
                record_loc, ""
            )

        to_refill = defaultdict(float)
        # diff add filtered
        all_product_ids = self._get_orderpoint_products().filtered(
            lambda prod: prod.replenish_by_lot
        )
        all_replenish_location_ids = self._get_orderpoint_locations()
        ploc_per_day = defaultdict(set)

        Move = self.env["stock.move"].with_context(active_test=False)
        Quant = self.env["stock.quant"].with_context(active_test=False)
        domain_quant, domain_move_in_loc, domain_move_out_loc = (
            all_product_ids._get_domain_locations_new(all_replenish_location_ids.ids)
        )
        domain_state = [
            ("state", "in", ("waiting", "confirmed", "assigned", "partially_available"))
        ]
        domain_product = [["product_id", "in", all_product_ids.ids]]

        domain_quant = expression.AND([domain_product, domain_quant])
        domain_move_in = expression.AND(
            [domain_product, domain_state, domain_move_in_loc]
        )
        domain_move_out = expression.AND(
            [domain_product, domain_state, domain_move_out_loc]
        )

        moves_in = defaultdict(list)

        # start diff
        # added lot_id in search. Now a tuple of +1 element
        for item in Move._read_group(
            domain_move_in,
            ["product_id", "location_dest_id", "location_final_id", "restrict_lot_id"],
            ["product_qty:sum"],
        ):
            moves_in[item[0]].append((item[1], item[2], item[3], item[4]))

        moves_out = defaultdict(list)
        for item in Move._read_group(
            domain_move_out,
            ["product_id", "location_id", "restrict_lot_id"],
            ["product_qty:sum"],
        ):
            moves_out[item[0]].append((item[1], item[2], item[3]))

        quants = defaultdict(list)
        for item in Quant._read_group(
            domain_quant, ["product_id", "location_id", "lot_id"], ["quantity:sum"]
        ):
            quants[item[0]].append((item[1], item[2], item[3]))
        # end diff

        # start diff:
        lots = set()
        for _, move in moves_out.items():
            lots.update([m[1] for m in move])
        for _, move in moves_in.items():
            lots.update([m[2] for m in move])
        for _, quant in quants.items():
            lots.update([q[1] for q in quant])
        # end diff

        rounding = {product.id: product.uom_id.rounding for product in all_product_ids}
        path = {
            loc: loc.parent_path
            for loc in self.env["stock.location"]
            .with_context(active_test=False)
            .search([("id", "child_of", all_replenish_location_ids.ids)])
        }
        for loc in all_replenish_location_ids:
            for product in all_product_ids:
                # start diff
                for lot in lots:
                    # diff: added one 0 in default value of get()
                    # diff: shift index. q[1] (sum) -> qt[2] (sum)
                    # because qt[1] is not lot_id
                    # diff: add an "and" clause for each lot_id
                    qty_available = sum(
                        q[2]
                        for q in quants.get(product, [(0, 0, 0)])
                        if is_parent_path_in(loc, path, q[0]) and q[1].id == lot.id
                    )
                    incoming_qty = sum(
                        m[3]
                        for m in moves_in.get(product, [(0, 0, 0, 0)])
                        if (
                            is_parent_path_in(loc, path, m[0])
                            or is_parent_path_in(loc, path, m[1])
                        )
                        and m[2].id == lot.id
                    )
                    outgoing_qty = sum(
                        m[2]
                        for m in moves_out.get(product, [(0, 0, 0)])
                        if is_parent_path_in(loc, path, m[0]) and m[1].id == lot.id
                    )
                    # end diff
                    if (
                        float_compare(
                            qty_available + incoming_qty - outgoing_qty,
                            0,
                            precision_rounding=rounding[product.id],
                        )
                        < 0
                    ):
                        # group product by lead_days and location in order to
                        # read virtual_available
                        # in batch
                        rules = product._get_rules_from_location(loc)
                        lead_days = rules.with_context(
                            bypass_delay_description=True
                        )._get_lead_days(product)[0]["total_delay"]
                        # diff: add lot_id in key.
                        # it will anhilate the optimization
                        # but we want to keep the algo quite close to the original
                        ploc_per_day[(lead_days, loc, lot)].add(product.id)

        # recompute virtual_available with lead days
        today = fields.datetime.now().replace(hour=23, minute=59, second=59)
        product_ids = set()
        location_ids = set()
        # start diff
        # diff add product_ids_by_lots
        lot_ids = set()
        for (days, loc, lot), prod_ids in ploc_per_day.items():
            # end diff
            products = self.env["product.product"].browse(prod_ids)
            qties = products.with_context(
                location=loc.id,
                lot_id=lot.id,  # diff
                to_date=today + relativedelta.relativedelta(days=days),
            ).read(["virtual_available"])
            for product, qty in zip(products, qties, strict=False):
                if (
                    float_compare(
                        qty["virtual_available"],
                        0,
                        precision_rounding=product.uom_id.rounding,
                    )
                    < 0
                ):
                    # diff: add lot_id in to_refill' key
                    to_refill[(qty["id"], loc.id, lot.id)] = qty["virtual_available"]
                    product_ids.add(qty["id"])
                    location_ids.add(loc.id)
                    # diff
                    lot_ids.add(lot.id)
            products.invalidate_recordset()
        if not to_refill:
            return to_refill

        # Remove incoming quantity from other origin than moves (e.g RFQ)
        product_ids = list(product_ids)
        location_ids = list(location_ids)
        # diff: remove qty_by_product_loc
        # diff: add qty_by_product_loc_lot
        qty_by_product_loc_lot, _ = (
            self.env["product.product"]
            .browse(product_ids)
            ._get_quantity_in_progress_by_lot(
                location_ids=location_ids, lot_ids=list(lot_ids)
            )
        )

        rounding = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )

        # start diff:
        # diff: remove orderpoint_by_product_location
        # because we orderpoint.qty_to_order don't make sense in our case
        # we need to compute by lot
        # end diff

        # diff add lot_id in to_refill
        for (product, location, lot_id), product_qty in to_refill.items():
            qty_in_progress = (
                qty_by_product_loc_lot.get((product, location, lot_id)) or 0.0
            )

            # diff: remove increment from orderpoint_by_product_location
            # Add qty to order for other orderpoint under this location.
            if not qty_in_progress:
                continue
            # diff: add lot_id in to_refill 'key
            to_refill[(product, location, lot_id)] = product_qty + qty_in_progress
        to_refill = {
            k: v
            for k, v in to_refill.items()
            if float_compare(v, 0.0, precision_digits=rounding) < 0.0
        }

        # diff: end of copy
        return to_refill
