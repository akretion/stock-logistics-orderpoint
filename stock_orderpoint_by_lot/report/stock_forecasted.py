# Copyright 2026 Akretion France (https://www.akretion.com/)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.osv import expression


class StockForecasted(models.AbstractModel):
    _inherit = "stock.forecasted_product_product"

    def _forecast_products(self, product_template_ids, product_ids):
        if product_template_ids:
            return (
                self.env["product.template"]
                .browse(product_template_ids)
                .product_variant_ids
            )
        return self.env["product.product"].browse(product_ids)

    def _forecast_by_lot(self, product_template_ids, product_ids):
        products = self._forecast_products(product_template_ids, product_ids)
        return bool(products) and all(products.mapped("replenish_by_lot"))

    def _get_report_data(self, product_template_ids=False, product_ids=False):
        report = self
        if not self._forecast_by_lot(product_template_ids, product_ids):
            report = self.with_context(lot_id=None)
        elif self.env.context.get("lot_id"):
            products = self._forecast_products(product_template_ids, product_ids)
            lot = self.env["stock.lot"].search(
                [
                    ("id", "=", self.env.context["lot_id"]),
                    ("product_id", "in", products.ids),
                    ("company_id", "in", [False, *self.env.companies.ids]),
                ]
            )
            if not lot:
                raise ValidationError(
                    _("The selected lot is not available for this product.")
                )
        return super(StockForecasted, report)._get_report_data(
            product_template_ids, product_ids
        )

    def _move_domain(self, product_template_ids, product_ids, wh_location_ids):
        in_domain, out_domain = super()._move_domain(
            product_template_ids, product_ids, wh_location_ids
        )
        lot_id = self.env.context.get("lot_id")
        if lot_id is not None and self._forecast_by_lot(
            product_template_ids, product_ids
        ):
            lot_domain = [("restrict_lot_id", "=", lot_id)]
            in_domain = expression.AND([in_domain, lot_domain])
            out_domain = expression.AND([out_domain, lot_domain])
        return in_domain, out_domain

    def _product_purchase_domain(self, product_template_ids, product_ids):
        domain = super()._product_purchase_domain(product_template_ids, product_ids)
        lot_id = self.env.context.get("lot_id")
        if lot_id is not None and self._forecast_by_lot(
            product_template_ids, product_ids
        ):
            domain = expression.AND([domain, [("lot_id", "=", lot_id)]])
        return domain

    def _forecast_lots(self, product_template_ids, product_ids, wh_location_ids):
        """Offer lots relevant to current stock, demand and graph history."""
        report = self.with_context(lot_id=None)
        products = report._forecast_products(product_template_ids, product_ids)
        lots = (
            self.env["stock.quant"]
            .search(
                [
                    ("product_id", "in", products.ids),
                    ("location_id", "in", wh_location_ids),
                    ("quantity", "!=", 0),
                ]
            )
            .lot_id
        )
        in_domain, out_domain = report._move_domain(
            product_template_ids, product_ids, wh_location_ids
        )
        lots |= (
            self.env["stock.move"]
            .search(
                expression.AND(
                    [
                        expression.OR([in_domain, out_domain]),
                        [("state", "not in", ["done", "cancel"])],
                    ]
                )
            )
            .restrict_lot_id
        )
        report_period = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("stock.report_stock_quantity_period", default="3")
        )
        # The graph reverses completed movements over its historical horizon.
        # Use actual move-line lots, including lots whose current stock is zero.
        lots |= (
            self.env["stock.move.line"]
            .search(
                [
                    ("product_id", "in", products.ids),
                    ("state", "=", "done"),
                    ("quantity_product_uom", "!=", 0),
                    (
                        "move_id.date",
                        ">=",
                        fields.Date.subtract(fields.Date.today(), months=report_period),
                    ),
                    "|",
                    "&",
                    ("location_id", "in", wh_location_ids),
                    ("location_dest_id", "not in", wh_location_ids),
                    "&",
                    ("location_id", "not in", wh_location_ids),
                    ("location_dest_id", "in", wh_location_ids),
                ]
            )
            .lot_id
        )
        purchase_lines = self.env["purchase.order.line"]
        if purchase_lines.has_access("read"):
            domain = report._product_purchase_domain(product_template_ids, product_ids)
            domain += [
                ("state", "in", ["draft", "sent", "to approve"]),
                ("company_id", "in", self.env.companies.ids),
                (
                    "order_id.picking_type_id.default_location_dest_id",
                    "in",
                    wh_location_ids,
                ),
            ]
            lots |= purchase_lines.search(domain).lot_id
        selected_lot = self.env.context.get("lot_id")
        if selected_lot:
            lots |= self.env["stock.lot"].browse(selected_lot)
        return self.env["stock.lot"].search(
            [
                ("id", "in", lots.ids),
                ("product_id", "in", products.ids),
                ("company_id", "in", [False, *self.env.companies.ids]),
            ],
            order="name, id",
        )

    def _get_report_header(self, product_template_ids, product_ids, wh_location_ids):
        result = super()._get_report_header(
            product_template_ids, product_ids, wh_location_ids
        )
        enabled = self._forecast_by_lot(product_template_ids, product_ids)
        result["lot_filter_enabled"] = enabled
        result["lots"] = (
            self._forecast_lots(
                product_template_ids, product_ids, wh_location_ids
            ).read(["name"])
            if enabled
            else []
        )
        return result

    def _get_report_lines(
        self,
        product_template_ids,
        product_ids,
        wh_location_ids,
        wh_stock_location,
        read=True,
    ):
        if not self._forecast_by_lot(product_template_ids, product_ids):
            return super()._get_report_lines(
                product_template_ids,
                product_ids,
                wh_location_ids,
                wh_stock_location,
                read=read,
            )
        lot_id = self.env.context.get("lot_id")
        lots = self._forecast_lots(product_template_ids, product_ids, wh_location_ids)
        lot_names = {lot.id: lot.name for lot in lots}
        bucket_ids = [lot_id] if lot_id is not None else [False, *lots.ids]
        lines = []
        for bucket_id in bucket_ids:
            # Reuse Odoo's reconciliation for each bucket independently. Its quant
            # query has no domain hook, so scope the quant override to this call.
            report = self.with_context(lot_id=bucket_id, _forecast_restrict_lot=True)
            bucket_lines = super(StockForecasted, report)._get_report_lines(
                product_template_ids,
                product_ids,
                wh_location_ids,
                wh_stock_location,
                read=read,
            )
            for line in bucket_lines:
                line.update(
                    lot_id=bucket_id,
                    lot_name=lot_names.get(bucket_id, _("No lot")),
                )
            lines.extend(bucket_lines)
        return lines
