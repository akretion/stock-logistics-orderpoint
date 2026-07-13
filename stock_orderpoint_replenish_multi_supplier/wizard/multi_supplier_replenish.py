from odoo import _, api, fields, models


class MultiSupplierReplenish(models.TransientModel):
    _name = "multi.supplier.replenish"

    product_replenish_ids = fields.Many2many(comodel_name="product.replenish")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            for p_id in vals["product_ids"]:
                product_replenish_id = (
                    self.env["product.replenish"]
                    .with_context(default_product_id=p_id)
                    .create([{}])
                )
                vals["product_replenish_ids"].append((4, product_replenish_id.id))

            vals.pop("product_ids")
        return super().create(vals_list)

    def action_multi_supplier_replenish(self):
        self.ensure_one()
        action = self.env.ref(
            "stock_orderpoint_replenish_multi_supplier.action_multi_supplier_replenish"
        )
        action["res_id"] = self.id
        return action._get_action_dict()
