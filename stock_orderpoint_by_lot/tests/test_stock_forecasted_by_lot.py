# Copyright 2026 Akretion France (https://www.akretion.com/)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockForecastedByLot(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].create(
            {"name": "Forecast by lot warehouse", "code": "FBL"}
        )
        cls.location = cls.warehouse.lot_stock_id
        cls.supplier = cls.env.ref("stock.stock_location_suppliers")
        cls.customer = cls.env.ref("stock.stock_location_customers")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Forecast by lot product",
                "is_storable": True,
                "tracking": "lot",
                "replenish_by_lot": True,
            }
        )
        cls.lot_a, cls.lot_b = cls.env["stock.lot"].create(
            [
                {
                    "name": name,
                    "product_id": cls.product.id,
                    "company_id": cls.env.company.id,
                }
                for name in ["Forecast lot A", "Forecast lot B"]
            ]
        )
        cls.report = cls.env["stock.forecasted_product_product"].with_context(
            warehouse_id=cls.warehouse.id
        )
        cls.vendor = cls.env["res.partner"].create({"name": "Forecast vendor"})

    def _move(self, quantity, lot=False, incoming=False, draft=False):
        move = self.env["stock.move"].create(
            {
                "name": self.id(),
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": quantity,
                "location_id": (self.supplier if incoming else self.location).id,
                "location_dest_id": (self.location if incoming else self.customer).id,
                "restrict_lot_id": lot.id if lot else False,
            }
        )
        if not draft:
            move._action_confirm()
        return move

    def _stock(self, quantity, lot=False):
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.location, quantity, lot_id=lot or None
        )

    def _purchase(self, quantity, lot=False):
        return self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "picking_type_id": self.warehouse.in_type_id.id,
                "order_line": [
                    fields.Command.create(
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "product_qty": quantity,
                            "product_uom": self.product.uom_id.id,
                            "price_unit": 1,
                            "date_planned": fields.Datetime.now(),
                            "lot_id": lot.id if lot else False,
                        }
                    )
                ],
            }
        )

    def _docs(self, **context):
        return self.report.with_context(**context).get_report_values(self.product.ids)[
            "docs"
        ]

    def test_selected_lot_and_no_lot_headers_and_drafts(self):
        self._stock(10, self.lot_a)
        self._stock(5)
        self._move(3, self.lot_a, incoming=True)
        self._move(2, incoming=True)
        self._move(4, self.lot_a)
        self._move(6)
        self._move(8, self.lot_a, incoming=True, draft=True)
        self._move(7, incoming=True, draft=True)
        po_a = self._purchase(11, self.lot_a)
        po_none = self._purchase(13)

        for lot_id, on_hand, incoming, outgoing, draft, purchase, po in [
            (self.lot_a.id, 10, 3, 4, 8, 11, po_a),
            (False, 5, 2, 6, 7, 13, po_none),
        ]:
            with self.subTest(lot_id=lot_id):
                docs = self._docs(lot_id=lot_id)
                self.assertTrue(docs["lot_filter_enabled"])
                self.assertEqual(docs["quantity_on_hand"], on_hand)
                self.assertEqual(docs["incoming_qty"], incoming)
                self.assertEqual(docs["outgoing_qty"], outgoing)
                self.assertEqual(
                    docs["virtual_available"], on_hand + incoming - outgoing
                )
                self.assertEqual(docs["draft_picking_qty"]["in"], draft)
                self.assertEqual(docs["draft_purchase_qty"], purchase)
                self.assertEqual(
                    [p["id"] for p in docs["draft_purchase_orders"]], po.ids
                )
                self.assertTrue(docs["lines"])
                self.assertTrue(all(line["lot_id"] == lot_id for line in docs["lines"]))

        aggregate = self._docs()
        explicit_all = self._docs(lot_id=None)
        self.assertEqual(aggregate["quantity_on_hand"], 15)
        self.assertEqual(aggregate["virtual_available"], 10)
        self.assertEqual(aggregate["draft_purchase_qty"], 24)
        self.assertEqual(aggregate["lines"], explicit_all["lines"])

    def test_aggregate_details_do_not_cover_other_lots(self):
        self._stock(10, self.lot_a)
        self._stock(2)
        self._move(4, self.lot_b)
        self._move(1, self.lot_b, incoming=True)
        self._move(5)
        self._move(8, self.lot_a, incoming=True)

        docs = self._docs()

        shortages = {
            line["lot_id"]: line["quantity"]
            for line in docs["lines"]
            if not line["replenishment_filled"]
        }
        self.assertEqual(shortages, {False: 3, self.lot_b.id: 3})
        self.assertEqual(
            sum(
                line["quantity"]
                for line in docs["lines"]
                if line["lot_id"] == self.lot_a.id
            ),
            8,
        )
        self.assertTrue(all(line["lot_name"] for line in docs["lines"]))
        for lot_id in [False, self.lot_a.id, self.lot_b.id]:
            self.assertEqual(
                self._docs(lot_id=lot_id)["lines"],
                [line for line in docs["lines"] if line["lot_id"] == lot_id],
            )

    def test_quant_context_is_private_to_forecast(self):
        self._stock(10, self.lot_a)
        self._stock(2)
        domain = [("product_id", "=", self.product.id)]
        quant = self.env["stock.quant"].with_context(lot_id=False)
        self.assertEqual(
            quant._read_group(domain, aggregates=["quantity:sum"]), [(12,)]
        )
        self.assertEqual(
            quant.with_context(_forecast_restrict_lot=True)._read_group(
                domain, aggregates=["quantity:sum"]
            ),
            [(2,)],
        )

    def test_lot_metadata_only_includes_relevant_lots(self):
        self._stock(1, self.lot_a)
        self._purchase(2, self.lot_b)
        unused = self.env["stock.lot"].create(
            {"name": "Historical lot", "product_id": self.product.id}
        )
        docs = self._docs()
        self.assertEqual(
            {lot["id"] for lot in docs["lots"]}, {self.lot_a.id, self.lot_b.id}
        )
        selected = self._docs(lot_id=unused.id)
        self.assertIn(unused.id, [lot["id"] for lot in selected["lots"]])

    def test_unrelated_lot_is_rejected(self):
        other_product = self.env["product.product"].create(
            {"name": "Unrelated forecast product", "is_storable": True}
        )
        lot = self.env["stock.lot"].create(
            {"name": "Unrelated lot", "product_id": other_product.id}
        )
        with self.assertRaises(ValidationError):
            self._docs(lot_id=lot.id)

    def test_historical_lot_with_zero_stock_is_available(self):
        # Restrictions are deliberately absent: historical graph buckets use
        # the lot actually moved, as recorded on completed move lines.
        for incoming in [True, False]:
            move = self._move(1, incoming=incoming, draft=True)
            self.env["stock.move.line"].create(
                {
                    "move_id": move.id,
                    "product_id": self.product.id,
                    "product_uom_id": self.product.uom_id.id,
                    "location_id": move.location_id.id,
                    "location_dest_id": move.location_dest_id.id,
                    "lot_id": self.lot_a.id,
                    "quantity": 1,
                    "picked": True,
                }
            )
            move._action_done()
            self.assertEqual(move.state, "done")
            move.date = fields.Datetime.subtract(fields.Datetime.now(), days=1)

        self.assertEqual(
            self.product.with_context(warehouse_id=self.warehouse.id).qty_available, 0
        )
        self.assertEqual({lot["id"] for lot in self._docs()["lots"]}, {self.lot_a.id})

    def test_ordinary_product_keeps_native_aggregate_report(self):
        self.product.replenish_by_lot = False
        self._stock(10, self.lot_a)
        self._move(4)
        docs = self._docs(lot_id=False)
        self.assertFalse(docs["lot_filter_enabled"])
        self.assertEqual(docs["lots"], [])
        self.assertEqual(docs["quantity_on_hand"], 10)
        self.assertEqual(docs["virtual_available"], 6)
        self.assertTrue(all(line["replenishment_filled"] for line in docs["lines"]))

    def test_orderpoint_navigation_preserves_bucket(self):
        for lot in [self.env["stock.lot"], self.lot_a]:
            orderpoint = self.env["stock.warehouse.orderpoint"].create(
                {
                    "product_id": self.product.id,
                    "warehouse_id": self.warehouse.id,
                    "location_id": self.location.id,
                    "lot_id": lot.id,
                    "trigger": "manual",
                }
            )
            context = orderpoint.action_product_forecast_report()["context"]
            self.assertEqual(context["lot_id"], lot.id)
            self.assertEqual(context["warehouse_id"], self.warehouse.id)
        self.product.replenish_by_lot = False
        self.assertNotIn(
            "lot_id", orderpoint.action_product_forecast_report()["context"]
        )

    def test_template_forecast_uses_lot_filter(self):
        self._stock(10, self.lot_a)
        self._stock(2)
        report = self.env["stock.forecasted_product_template"].with_context(
            warehouse_id=self.warehouse.id, lot_id=False
        )
        docs = report.get_report_values(self.product.product_tmpl_id.ids)["docs"]
        self.assertTrue(docs["lot_filter_enabled"])
        self.assertEqual(docs["quantity_on_hand"], 2)
