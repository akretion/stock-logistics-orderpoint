# Copyright 2026 Akretion France (https://www.akretion.com/)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from datetime import datetime, time, timedelta

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockOrderpointByLotNoLot(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].create(
            {"name": "Orderpoint by lot test warehouse", "code": "OBL"}
        )
        cls.warehouse.lot_stock_id.replenish_location = False
        cls.location = cls.env["stock.location"].create(
            {
                "name": "Orderpoint by lot replenishment location",
                "location_id": cls.warehouse.lot_stock_id.id,
                "replenish_location": True,
            }
        )
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Product replenished by lot",
                "is_storable": True,
                "tracking": "lot",
                "replenish_by_lot": True,
            }
        )
        cls.lot_a = cls.env["stock.lot"].create(
            {
                "name": "Lot A",
                "product_id": cls.product.id,
                "company_id": cls.env.company.id,
            }
        )

    def _create_move(self, source, destination, quantity, lot=False):
        move = self.env["stock.move"].create(
            {
                "name": self.id(),
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": quantity,
                "location_id": source.id,
                "location_dest_id": destination.id,
                "restrict_lot_id": lot.id if lot else False,
            }
        )
        move._action_confirm()
        return move

    def _create_orderpoint(self, product=None, lot=False):
        product = product or self.product
        return self.env["stock.warehouse.orderpoint"].create(
            {
                "name": self.id(),
                "product_id": product.id,
                "warehouse_id": self.warehouse.id,
                "location_id": self.location.id,
                "lot_id": lot.id if lot else False,
                "product_min_qty": 0,
                "product_max_qty": 0,
                "trigger": "manual",
            }
        )

    def test_no_lot_deficit_creates_no_lot_orderpoint(self):
        self._create_move(self.location, self.customer_location, 4)
        self._create_move(self.supplier_location, self.location, 4, self.lot_a)

        to_refill = self.env["stock.warehouse.orderpoint"]._get_qty_to_order_by_lot()
        self.assertEqual(
            to_refill,
            {(self.product.id, self.location.id, False): -4},
        )

        self.env["stock.warehouse.orderpoint"]._create_missing_orderpoint_by_lot()
        orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [
                ("product_id", "=", self.product.id),
                ("location_id", "=", self.location.id),
                ("lot_id", "=", False),
            ]
        )
        self.assertEqual(len(orderpoint), 1)
        self.assertEqual(orderpoint.qty_forecast, -4)
        self.assertEqual(orderpoint.qty_to_order, 4)

    def test_named_lot_deficit_does_not_mutate_no_lot_forecast(self):
        no_lot_orderpoint = self._create_orderpoint()
        self._create_move(self.location, self.customer_location, 4)
        self._create_move(self.location, self.customer_location, 3, self.lot_a)
        self.assertEqual(no_lot_orderpoint.qty_forecast, -4)

        self.env["stock.warehouse.orderpoint"]._create_missing_orderpoint_by_lot()

        self.assertEqual(no_lot_orderpoint.qty_forecast, -4)
        self.assertEqual(no_lot_orderpoint.qty_to_order, 4)
        named_orderpoint = self.env["stock.warehouse.orderpoint"].search(
            [
                ("product_id", "=", self.product.id),
                ("location_id", "=", self.location.id),
                ("lot_id", "=", self.lot_a.id),
            ]
        )
        self.assertEqual(len(named_orderpoint), 1)
        self.assertEqual(named_orderpoint.qty_forecast, -3)

    def test_ordinary_product_orderpoint_keeps_aggregate_context(self):
        self.product.replenish_by_lot = False
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.location, 10, lot_id=self.lot_a
        )
        self._create_move(self.location, self.customer_location, 4)
        orderpoint = self._create_orderpoint()

        context = orderpoint._get_product_context()

        self.assertNotIn("lot_id", context)
        self.assertEqual(orderpoint.qty_forecast, 6)
        self.assertEqual(orderpoint.qty_to_order, 0)

    def test_visibility_days_are_forwarded(self):
        orderpoint = self._create_orderpoint()

        context = orderpoint._get_product_context(visibility_days=5)

        self.assertEqual(context["lot_id"], False)
        self.assertEqual(
            context["to_date"],
            datetime.combine(orderpoint.lead_days_date + timedelta(days=5), time.max),
        )
