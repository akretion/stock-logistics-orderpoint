# Copyright 2025 Akretion France (https://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>

from odoo import api, models


# class ProcurementGroup(models.Model):
#     _inherit = "procurement.group"
#
#     @api.model
#     def run(self, procurements, raise_user_error=True):
#         new_procurements = []
#         for procurement in procurements:
#             if not procurement.product_id.replenish_by_lot:
#                 # exclude product not configured
#                 new_procurements.append(procurement)
#                 continue
#             if procurement.values.get("restrict_lot_id", False):
#                 # procurement not run from orderpoint; skip
#                 new_procurements.append(procurement)
#                 continue
#
#             if not self.env.context.get("from_orderpoint", False):
#                 # procurement not run from orderpoint; skip
#                 new_procurements.append(procurement)
#                 continue
#
#             lot_id = procurement.values.get("lot_id", False)
#             # by_lots = {lot_id: qty, lot_id2: qty}
#             # example: {32:-2, False:-1}
#             # = lot(32) qty 2, no lot qty 1
#             # it is expected to have a mix of restricted and not
#             # restricted lots
#             new_procurement = self.env["procurement.group"].Procurement(
#                 procurement.product_id,
#                 -1 * qty,
#                 procurement.product_uom,
#                 procurement.location_id,
#                 procurement.name,
#                 procurement.origin,
#                 procurement.company_id,
#                 procurement.values.copy(),
#             )
#             if lot_id:
#                 new_procurement.values["restrict_lot_id"] = lot_id
#             new_procurements.append(new_procurement)
#         return super().run(new_procurements, raise_user_error)
