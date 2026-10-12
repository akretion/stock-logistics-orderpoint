# Copyright 2026 Akretion France (https://www.akretion.com/)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from datetime import UTC, datetime, timedelta

from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestStockQuantityByLot(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].create(
            {"name": "Lot forecast warehouse", "code": "LFR"}
        )
        cls.location = cls.warehouse.lot_stock_id
        cls.supplier = cls.env.ref("stock.stock_location_suppliers")
        cls.customer = cls.env.ref("stock.stock_location_customers")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Lot forecast test product",
                "is_storable": True,
                "tracking": "lot",
                "replenish_by_lot": True,
                "uom_id": cls.env.ref("uom.product_uom_unit").id,
                "uom_po_id": cls.env.ref("uom.product_uom_unit").id,
            }
        )
        cls.lot_a, cls.lot_b = cls.env["stock.lot"].create(
            [
                {
                    "name": name,
                    "product_id": cls.product.id,
                    "company_id": cls.env.company.id,
                }
                for name in ("Forecast A", "Forecast B")
            ]
        )
        cls.today = datetime.now(UTC).date()
        cls.report = cls.env["report.stock.quantity.by.lot"]

    def _move(self, source, destination, quantity, lot=False, days=0, **values):
        move = self.env["stock.move"].create(
            {
                "name": self.id(),
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": quantity,
                "location_id": source.id,
                "location_dest_id": destination.id,
                "restrict_lot_id": lot.id if lot else False,
                **values,
            }
        )
        move._action_confirm()
        move.date = datetime.combine(
            self.today + timedelta(days=days), datetime.min.time()
        )
        return move

    def _quant(self, quantity, lot=False, location=None):
        self.env["stock.quant"]._update_available_quantity(
            self.product, location or self.location, quantity, lot_id=lot
        )

    def _quantities(self, days=0, state="forecast", warehouse=None):
        return {
            lot.id: quantity
            for lot, quantity in self.report._read_group(
                [
                    ("product_id", "=", self.product.id),
                    ("warehouse_id", "=", (warehouse or self.warehouse).id),
                    ("date", "=", self.today + timedelta(days=days)),
                    ("state", "=", state),
                ],
                ["lot_id"],
                ["product_qty:sum"],
            )
        }

    def _assert_native_parity(self):
        domain = [("product_id", "=", self.product.id)]
        grouping = ["date:day", "state", "warehouse_id", "company_id"]
        native = self.env["report.stock.quantity"]._read_group(
            domain, grouping, ["product_qty:sum"]
        )
        by_lot = self.report._read_group(domain, grouping, ["product_qty:sum"])
        self.assertEqual(set(native), set(by_lot))

    def test_pending_moves_and_quants_keep_no_lot_separate(self):
        self._quant(10)
        self._quant(20, self.lot_a)
        self._quant(30, self.lot_b)
        self._move(self.location, self.customer, 4)
        self._move(self.supplier, self.location, 7, self.lot_a)
        self._move(self.location, self.customer, 5, self.lot_b)
        # A future receipt must not affect today's forecast.
        self._move(self.supplier, self.location, 2, self.lot_b, days=2)

        self.assertEqual(
            self._quantities(), {False: 6, self.lot_a.id: 27, self.lot_b.id: 25}
        )
        self.assertEqual(self._quantities(state="in"), {self.lot_a.id: 7})
        self.assertEqual(self._quantities(state="out"), {False: -4, self.lot_b.id: -5})
        self.assertEqual(self._quantities(days=2)[self.lot_b.id], 27)
        self._assert_native_parity()

    def test_done_move_uses_actual_line_lots_and_uom(self):
        move = self._move(self.supplier, self.location, 18)
        move.move_line_ids.unlink()
        dozen = self.env.ref("uom.product_uom_dozen")
        self.env["stock.move.line"].create(
            [
                {
                    "move_id": move.id,
                    "product_id": self.product.id,
                    "product_uom_id": dozen.id,
                    "quantity": quantity,
                    "lot_id": lot.id,
                    "location_id": self.supplier.id,
                    "location_dest_id": self.location.id,
                }
                for lot, quantity in ((self.lot_a, 1), (self.lot_b, 0.5))
            ]
        )
        move.picked = True
        move._action_done()
        # Move completion replaces the scheduled date; set the historical date
        # after completing the real stock operation.
        move.date = datetime.combine(
            self.today - timedelta(days=2), datetime.min.time()
        )

        self.assertFalse(move.restrict_lot_id)
        self.assertEqual(self._quantities(), {self.lot_a.id: 12, self.lot_b.id: 6})
        self.assertEqual(
            self._quantities(days=-3), {self.lot_a.id: 0, self.lot_b.id: 0}
        )
        self.assertEqual(
            self._quantities(days=-2), {self.lot_a.id: 12, self.lot_b.id: 6}
        )
        self._assert_native_parity()

    def test_internal_and_interwarehouse_moves(self):
        other = self.env["stock.warehouse"].create(
            {"name": "Lot forecast destination", "code": "LFD"}
        )
        child = self.env["stock.location"].create(
            {"name": "Forecast shelf", "location_id": self.location.id}
        )
        self._quant(10, self.lot_a)
        self._move(self.location, child, 2, self.lot_a)
        self._move(self.location, other.lot_stock_id, 3, self.lot_a)

        self.assertEqual(self._quantities(), {self.lot_a.id: 7})
        self.assertEqual(self._quantities(warehouse=other), {self.lot_a.id: 3})
        self._assert_native_parity()

    def test_pending_move_uses_final_location(self):
        other = self.env["stock.warehouse"].create(
            {"name": "Lot forecast final destination", "code": "LFF"}
        )
        self._quant(10, self.lot_b)
        self._move(
            self.location,
            self.warehouse.wh_output_stock_loc_id,
            3,
            self.lot_b,
            location_final_id=other.lot_stock_id.id,
        )

        self.assertEqual(self._quantities(), {self.lot_b.id: 7})
        self.assertEqual(self._quantities(warehouse=other), {self.lot_b.id: 3})
        self._assert_native_parity()

    def test_company_rule_and_read_only_access(self):
        company = self.env["res.company"].create({"name": "Lot forecast other company"})
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", company.id)], limit=1
        )
        self.assertTrue(warehouse)
        self._quant(4)
        self._quant(9, location=warehouse.lot_stock_id)
        user = new_test_user(
            self.env,
            login="lot_forecast_reader",
            groups="base.group_user,stock.group_stock_user",
            company_id=self.env.company.id,
            company_ids=[(6, 0, [self.env.company.id, company.id])],
        )
        report = self.report.with_user(user).with_context(
            allowed_company_ids=[self.env.company.id]
        )
        domain = [
            ("product_id", "=", self.product.id),
            ("date", "=", self.today),
            ("state", "=", "forecast"),
        ]
        quantities = report._read_group(domain, ["company_id"], ["product_qty:sum"])
        self.assertEqual(quantities, [(self.env.company, 4)])
        quantities = report.with_context(
            allowed_company_ids=[self.env.company.id, company.id]
        )._read_group(domain, ["company_id"], ["product_qty:sum"])
        self.assertEqual(dict(quantities), {self.env.company: 4, company: 9})
        self.assertTrue(report.check_access_rights("read", raise_exception=False))
        for operation in ("create", "write", "unlink"):
            self.assertFalse(
                report.check_access_rights(operation, raise_exception=False)
            )
