from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockOrderpointReplenishMultiSupplier(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse_a = cls.env["stock.warehouse"].create(
            {"name": "Multi supplier test warehouse A", "code": "MSA"}
        )
        cls.warehouse_b = cls.env["stock.warehouse"].create(
            {"name": "Multi supplier test warehouse B", "code": "MSB"}
        )
        cls.vendors = cls.env["res.partner"].create(
            [{"name": "Test vendor A"}, {"name": "Test vendor B"}]
        )

    def _create_product(self, name, vendor_count):
        return self.env["product.product"].create(
            {
                "name": name,
                "is_storable": True,
                "seller_ids": [
                    Command.create(
                        {
                            "partner_id": vendor.id,
                            "price": 10,
                        }
                    )
                    for vendor in self.vendors[:vendor_count]
                ],
            }
        )

    def _create_orderpoint(self, product, warehouse, maximum=0):
        return self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": product.id,
                "warehouse_id": warehouse.id,
                "location_id": warehouse.lot_stock_id.id,
                "product_min_qty": 0,
                "product_max_qty": maximum,
                "qty_to_order_manual": 1,
                "trigger": "manual",
            }
        )

    def test_mixed_selection_uses_surviving_multi_supplier_warehouse(self):
        single_orderpoint = self._create_orderpoint(
            self._create_product("Single supplier product", 1), self.warehouse_a
        )
        multi_product = self._create_product("Multi supplier product", 2)
        multi_orderpoint = self._create_orderpoint(multi_product, self.warehouse_b)

        with patch.object(
            type(single_orderpoint), "_procure_orderpoint_confirm", return_value=None
        ):
            action = (single_orderpoint | multi_orderpoint).action_replenish()

        self.assertFalse(single_orderpoint.exists())
        self.assertTrue(multi_orderpoint.exists())
        wizard = self.env["multi.supplier.replenish"].browse(action["res_id"])
        self.assertEqual(wizard.warehouse_id, self.warehouse_b)
        self.assertEqual(wizard.product_replenish_ids.product_id, multi_product)

    def test_all_single_supplier_preserves_result_and_force_to_max(self):
        orderpoint = self._create_orderpoint(
            self._create_product("Force to max product", 1),
            self.warehouse_a,
            maximum=7,
        )
        procured_quantities = []

        def record_quantity(orderpoints, **kwargs):
            procured_quantities.append(orderpoints.qty_to_order)

        with patch.object(
            type(orderpoint), "_procure_orderpoint_confirm", record_quantity
        ):
            result = orderpoint.action_replenish(force_to_max=True)

        self.assertFalse(result)
        self.assertEqual(procured_quantities, [7])

    def test_multi_warehouse_error_precedes_single_supplier_replenishment(self):
        single_orderpoint = self._create_orderpoint(
            self._create_product("Unprocessed single supplier product", 1),
            self.warehouse_a,
        )
        multi_orderpoint_a = self._create_orderpoint(
            self._create_product("Multi supplier product A", 2), self.warehouse_a
        )
        multi_orderpoint_b = self._create_orderpoint(
            self._create_product("Multi supplier product B", 2), self.warehouse_b
        )

        with (
            patch.object(
                type(single_orderpoint),
                "_procure_orderpoint_confirm",
                return_value=None,
            ) as procure,
            self.assertRaises(UserError),
        ):
            (
                single_orderpoint | multi_orderpoint_a | multi_orderpoint_b
            ).action_replenish()

        procure.assert_not_called()
        self.assertTrue(single_orderpoint.exists())
