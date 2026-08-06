from odoo import _, api, fields, models


class MultiSupplierReplenish(models.TransientModel):
    _name = "multi.supplier.replenish"
    _check_company_auto = True

    product_replenish_ids = fields.Many2many(comodel_name="product.replenish")
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        required=True,
        check_company=True,
    )
    company_id = fields.Many2one("res.company")

    @api.model
    def get_product_ids_and_lot_from_product(
        self, product_id=None, product_tmpl_id=None
    ):

        product_ids = []
        if product_tmpl_id:
            product_ids = product_tmpl_id.product_variant_ids
        if product_id:
            product_ids = product_id

        lot_ids = self.env["stock.lot"].search(
            [("product_id", "in", product_ids.mapped("id"))]
        )

        product_ids_lot_ids = []
        for lot_id in lot_ids:
            forecasted_quantity = lot_id.product_id.with_context(
                warehouse_id=self.warehouse_id.id,
                lot_id=lot_id.id,
            ).virtual_available
            if forecasted_quantity < 0:
                product_ids_lot_ids.append((lot_id.product_id.id, lot_id.id))

        return product_ids_lot_ids

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            for p_id, l_id in vals["product_ids_lot_ids"]:
                product_replenish_id = (
                    self.env["product.replenish"]
                    .with_context(default_product_id=p_id)
                    .create([{"lot_id": l_id}])
                )
                product_replenish_id._onchange_product_id()
                vals["product_replenish_ids"].append((4, product_replenish_id.id))

            vals.pop("product_ids_lot_ids")
        return super().create(vals_list)

    def launch_replenishment(self):
        for replenish in self.product_replenish_ids:
            replenish.launch_replenishment()

    def action_multi_supplier_replenish(self):
        self.ensure_one()
        action = self.env.ref(
            "stock_orderpoint_replenish_multi_supplier.action_multi_supplier_replenish"
        )
        action["res_id"] = self.id
        return action._get_action_dict()
