# Copyright 2025 Akretion France (https://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>

from odoo import api, models


class StockRule(models.Model):
    _inherit = "stock.rule"

    @api.model
    def _get_procurements_to_merge_groupby(self, procurement):
        # do not merge lines with a different restrict lot
        res = super()._get_procurements_to_merge_groupby(procurement)
        return res, procurement.values.get("restrict_lot_id")
