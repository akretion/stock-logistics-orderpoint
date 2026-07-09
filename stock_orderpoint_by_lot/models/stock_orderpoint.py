# Copyright 2025 Akretion France (https://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>

from collections import defaultdict

from dateutil import relativedelta

from odoo import SUPERUSER_ID, _, fields, models
from odoo.osv import expression
from odoo.tools import float_compare


# TODO(franz): right now this is not really greate it does not create
# the orderpoint by lot however it replenishes the orderpoint by lot
# which is great
# However I think that the right version of this should be to add a field
# lot_id to the stock.orderpoint model redefine the _get_orderpoint_action
# method and splitting the orderpoint by lot
# To do this we would need to redefine the _get_qty_to_order method to
# add the lot_id to the context of the read([virtual_available])
# One issue is that if you have several lot asking for replenishment there is only one
# orderpoint for all the lot_ids and if you can't order only for one lot
# furthermore all the commented code does nothing for the model
class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    replenish_by_lot = fields.Boolean(related="product_id.replenish_by_lot")
    lot_id = fields.Many2one(comodel_name="stock.lot")

    def _prepare_procurement_values(self, date=False, group=False):
        # add a replenish_by_lots in values
        # like { lot1: qty1, lot5: qty2}
        res = super()._prepare_procurement_values(date, group)
        if not self.replenish_by_lot:
            # exit early
            return res
        res["restrict_lot_id"] = self.lot_id.id
        return res

    def _get_orderpoint_action(self):
        action = super()._get_orderpoint_action()
        self._create_missing_orderpoint_by_lot()
        return action

    def _get_product_context(self, visibility_days=0):
        context = super()._get_product_context()
        context["lot_id"] = self.lot_id.id
        return context

    def _create_missing_orderpoint_by_lot(self):
        orderpoints = self.search([["replenish_by_lot", "=", True]])
        to_refill = orderpoints._get_qty_to_order_by_lot()
        product_ids = orderpoints.product_id.ids

        # copy pasted from super()
        orderpoint_by_product_location = (
            self.env["stock.warehouse.orderpoint"]
            .with_context(active_test=False)
            ._read_group(
                [("id", "in", orderpoints.ids), ("product_id", "in", product_ids)],
                ["product_id", "location_id"],
                ["id:recordset"],
            )
        )
        orderpoint_by_product_location = {
            (product.id, location.id): orderpoint
            for product, location, orderpoint in orderpoint_by_product_location
        }
        # diff: add orderpoint_to_create
        orderpoint_to_create = set()
        orderpoint_values_list = []
        for (product, location_id, lot_id), product_qty in to_refill.items():
            orderpoint = orderpoint_by_product_location.get((product, location_id))
            if orderpoint:
                orderpoint.qty_forecast += product_qty
            # start diff:
            # we loop on lot, so an op can be created for the first lot
            # stop early for subsequent lots
            elif (product, location_id) in orderpoint_to_create:
                # op already created
                continue
            # end of diff:
            else:
                orderpoint_values = self.env[
                    "stock.warehouse.orderpoint"
                ]._get_orderpoint_values(product, location_id)
                location = self.env["stock.location"].browse(location_id)
                orderpoint_values.update(
                    {
                        "name": _("Replenishment Report"),
                        "lot_id": lot_id,
                        "warehouse_id": location.warehouse_id.id
                        or self.env["stock.warehouse"]
                        .search([("company_id", "=", location.company_id.id)], limit=1)
                        .id,
                        "company_id": location.company_id.id,
                    }
                )
                orderpoint_values_list.append(orderpoint_values)
                # diff add in orderpoint_to_create
                # flag op has in creation
                orderpoint_to_create.add((product, location_id))

        orderpoints = (
            self.env["stock.warehouse.orderpoint"]
            .with_user(SUPERUSER_ID)
            .create(orderpoint_values_list)
        )
        for orderpoint in orderpoints:
            orderpoint._set_default_route_id()
            orderpoint.qty_multiple = orderpoint._get_qty_multiple_to_order()

    # EDIT(franz): This is a version of _compute_qty_to_order_computed
    # That does not tank the performance of the stock.orderpoint list view
    # in the old method calling _get_qty_to_order for each orderpoint
    # was calling _get_qty_to_order_by_lot which compute read all the move
    # and quant from the db which is prohibitively slow (0.2s) * the number of
    # orderpoint
    # # api.depends looks not needed on inherited
    # def _compute_qty_to_order_computed(self):
    #     # TODO: compute "correctly" qty_focasted instead
    #     orderpoints_by_lot = self.filtered(lambda o: o.replenish_by_lot)
    #
    #     orderpoint_no_lot = self - orderpoints_by_lot
    #     res = super(
    #         StockWarehouseOrderpoint, orderpoint_no_lot
    #     )._compute_qty_to_order_computed()
    #
    #     qty_by_lot = orderpoints_by_lot._get_qty_to_order_by_lot()
    #     for orderpoint in orderpoints_by_lot:
    #         sum_qty = 0
    #         for prod_loc_lot, qty in qty_by_lot.items():
    #             if prod_loc_lot[0] == orderpoint.product_id.id:
    #                 sum_qty += qty
    #             else:
    #                 orderpoint.qty_to_order_computed = False
    #                 breakpoint()
    #         orderpoint.qty_to_order_computed = -1 * sum_qty
    #     return res

    # # api.depends looks not needed on inherited
    # def _compute_qty_to_order_computed(self):
    #     res = super()._compute_qty_to_order_computed()
    #
    #     # TODO: compute "correctly" qty_focasted instead
    #     orderpoints = self.filtered(lambda o: o.replenish_by_lot)
    #
    #     qty_in_progress_by_orderpoint = orderpoints._quantity_in_progress()
    #     for orderpoint in orderpoints:
    #         orderpoint.qty_to_order_computed = orderpoint._get_qty_to_order(
    #             qty_in_progress_by_orderpoint=qty_in_progress_by_orderpoint
    #         )
    #     return res
    #
    # def _get_qty_to_order(
    #     self, force_visibility_days=False, qty_in_progress_by_orderpoint=None
    # ):
    #     self.ensure_one()
    #     if not self.replenish_by_lot:
    #         return super()._get_qty_to_order(
    #             force_visibility_days, qty_in_progress_by_orderpoint
    #         )
    #     # filter by our product_id
    #     qty_by_lot = [
    #         qty
    #         for prod_loc_lot, qty in self._get_qty_to_order_by_lot().items()
    #         if prod_loc_lot[0] == self.product_id.id
    #     ]
    #     return -1 * sum(qty_by_lot)

    def _get_orderpoint_products(self):
        result = super()._get_orderpoint_products()
        if self.env.context.get("by_lot"):
            result = result.filtered(lambda prod: prod.replenish_by_lot)
        else:
            result = result.filtered(lambda prod: not prod.replenish_by_lot)
        return result

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
        all_product_ids = (
            self.with_context(by_lot=True)
            ._get_orderpoint_products()
            .filtered(lambda prod: prod.replenish_by_lot)
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
        # _product_id because _ is shadowed (import)
        lots = set()
        for _product_id, move in moves_out.items():
            lots.update([m[1] for m in move])
        for _product_id, move in moves_in.items():
            lots.update([m[2] for m in move])
        for _product_id, quant in quants.items():
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
        qty_by_product_loc_lot, _qty_by_product_wh_lot = (
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
