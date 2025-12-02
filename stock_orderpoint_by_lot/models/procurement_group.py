# Copyright 2025 Akretion France (https://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>

from odoo import api, models


class ProcurementGroup(models.Model):
    _inherit = "procurement.group"

    @api.model
    def run(self, procurements, raise_user_error=True):
        new_procurements = []
        for procurement in procurements:
            if not procurement.product_id.replenish_by_lot:
                # exclude product not configured
                new_procurements.append(procurement)
                continue
            if procurement.values.get("restrict_lot_id", False):
                # procurement not run from orderpoint; skip
                new_procurements.append(procurement)
                continue

            by_lots = procurement.values.get("replenish_by_lots", {})
            # by_lots = {lot_id: qty, lot_id2: qty}
            # if by_lots is {} it means nothing to procure

            for lot_id, qty in by_lots.items():
                new_procurement = self.env["procurement.group"].Procurement(
                    procurement.product_id,
                    -1 * qty,
                    procurement.product_uom,
                    procurement.location_id,
                    procurement.name,
                    procurement.origin,
                    procurement.company_id,
                    procurement.values.copy(),
                )

                new_procurement.values["restrict_lot_id"] = lot_id
                new_procurements.append(new_procurement)
        return super().run(new_procurements, raise_user_error)
