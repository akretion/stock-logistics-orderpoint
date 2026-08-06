from odoo import _, api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def action_open_multi_supplier_replenish(self):
        self.ensure_one()
        MultiSupplier = self.env["multi.supplier.replenish"]
        product_ids_lot_ids = MultiSupplier.get_product_ids_and_lot_from_product(
            product_tmpl_id=self
        )

        wizard = self.env["multi.supplier.replenish"].create(
            [
                {
                    "product_ids_lot_ids": product_ids_lot_ids,
                    "product_replenish_ids": [],
                },
            ]
        )
        return wizard.action_multi_supplier_replenish()


class ProductProduct(models.Model):
    _inherit = "product.product"

    def action_open_multi_supplier_replenish(self):
        self.ensure_one()
        MultiSupplier = self.env["multi.supplier.replenish"]
        product_ids_lot_ids = MultiSupplier.get_product_ids_and_lot_from_product(
            product_id=self
        )

        wizard = self.env["multi.supplier.replenish"].create(
            [
                {
                    "product_ids_lot_ids": product_ids_lot_ids,
                    "product_replenish_ids": [],
                },
            ]
        )
        return wizard.action_multi_supplier_replenish()
