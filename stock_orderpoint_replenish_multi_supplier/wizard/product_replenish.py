from odoo import _, api, fields, models


class ProductReplenish(models.TransientModel):
    _inherit = "product.replenish"

    lot_id = fields.Many2one(comodel_name="stock.lot")

    def _prepare_run_values(self):
        values = super()._prepare_run_values()
        values["restrict_lot_id"] = self.lot_id.id
        return values

    @api.onchange("product_id", "warehouse_id", "lot_id")
    def _onchange_product_id(self):
        super()._onchange_product_id()

    @api.depends("warehouse_id", "product_id", "lot_id")
    def _compute_forecasted_quantity(self):
        for rec in self:
            if rec.lot_id:
                rec.forecasted_quantity = rec.product_id.with_context(
                    warehouse_id=rec.warehouse_id.id, lot_id=rec.lot_id.id
                ).virtual_available
            else:
                super(ProductReplenish, rec)._compute_forecasted_quantity()
