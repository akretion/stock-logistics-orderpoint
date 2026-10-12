# Copyright 2026 Akretion France (https://www.akretion.com/)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import api, models
from odoo.osv import expression


class StockQuant(models.Model):
    _inherit = "stock.quant"

    @api.model
    def _read_group(
        self,
        domain,
        groupby=(),
        aggregates=(),
        having=(),
        offset=0,
        limit=None,
        order=None,
    ):
        if (
            self.env.context.get("_forecast_restrict_lot")
            and self.env.context.get("lot_id") is not None
        ):
            domain = expression.AND(
                [domain, [("lot_id", "=", self.env.context["lot_id"])]]
            )
        return super()._read_group(
            domain, groupby, aggregates, having, offset, limit, order
        )
