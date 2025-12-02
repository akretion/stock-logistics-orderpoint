# Copyright 2025 Akretion France (https://www.akretion.com/)
# @author: Raphaël Reverdy <raphael.reverdy@akretion.com>

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    replenish_by_lot = fields.Boolean(help="Replenish by lot")
