# Copyright 2026 Akretion France (https://www.akretion.com/)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from typing import ClassVar

from odoo import fields, models, tools


class ReportStockQuantityByLot(models.Model):
    _name = "report.stock.quantity.by.lot"
    _inherit = "report.stock.quantity"
    _description = "Stock Quantity Report by Lot"
    _auto = False

    lot_id = fields.Many2one("stock.lot", string="Lot/Serial Number", readonly=True)

    _depends: ClassVar = {
        "product.product": ["product_tmpl_id"],
        "product.template": ["is_storable", "uom_id"],
        "stock.location": ["parent_path", "usage"],
        "stock.move": [
            "company_id",
            "date",
            "location_dest_id",
            "location_final_id",
            "location_id",
            "product_id",
            "product_qty",
            "state",
            "restrict_lot_id",
        ],
        "stock.move.line": ["move_id", "product_id", "lot_id", "quantity_product_uom"],
        "stock.quant": [
            "company_id",
            "location_id",
            "product_id",
            "quantity",
            "lot_id",
        ],
        "stock.warehouse": ["view_location_id"],
    }

    def init(self):
        # Keep the native report intact. Pending demand belongs to its restricted
        # lot; completed quantities belong to the lots actually moved, in the
        # product's UoM. Inline the move CTEs so product/lot domains reach sources.
        # Like the native aggregate report, ids identify a contributing source;
        # they are not unique across dates (this model is only used by graphs).
        tools.drop_view_if_exists(self.env.cr, self._table)
        query = """
CREATE or REPLACE VIEW report_stock_quantity_by_lot AS (
WITH
    warehouse_cte AS(
        SELECT sl.id as sl_id, w.id as w_id
        FROM stock_location sl
        LEFT JOIN stock_warehouse w
            ON sl.parent_path::text like concat('%%/', w.view_location_id, '/%%')
    ),
    move_source AS NOT MATERIALIZED (
        SELECT m.id, m.product_id, m.restrict_lot_id AS lot_id,
            m.product_qty, 0::numeric AS quantity, m.date, m.state,
            m.company_id, m.location_id,
            COALESCE(m.location_final_id, m.location_dest_id) AS location_dest_id
        FROM stock_move m
        WHERE m.state IN ('waiting', 'confirmed', 'partially_available', 'assigned')
            AND m.product_qty != 0
        UNION ALL
        SELECT ml.id, ml.product_id, ml.lot_id,
            0::numeric AS product_qty, ml.quantity_product_uom AS quantity,
            m.date, m.state, m.company_id, m.location_id, m.location_dest_id
        FROM stock_move m
        JOIN stock_move_line ml ON ml.move_id = m.id
        WHERE m.state = 'done' AND ml.quantity_product_uom != 0
            AND m.date >= ((now() at time zone 'utc')::date
                - interval '%(report_period)s month')
    ),
    existing_sm AS NOT MATERIALIZED (
        SELECT m.id, m.product_id, pt.id AS tmpl_id, m.lot_id,
            m.product_qty, m.quantity, m.date, m.state, m.company_id,
            source.w_id AS whs_id, dest.w_id AS whd_id
        FROM move_source m
        LEFT JOIN warehouse_cte source ON source.sl_id = m.location_id
        LEFT JOIN warehouse_cte dest ON dest.sl_id = m.location_dest_id
        JOIN product_product pp ON pp.id = m.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        WHERE pt.is_storable = true
            AND (source.w_id IS NOT NULL OR dest.w_id IS NOT NULL)
            AND (source.w_id IS NULL OR dest.w_id IS NULL
                OR source.w_id <> dest.w_id)
    ),
    all_sm (id, product_id, tmpl_id, lot_id, product_qty, quantity, date,
            state, company_id, whs_id, whd_id) AS NOT MATERIALIZED (
        SELECT sm.id, sm.product_id, sm.tmpl_id, sm.lot_id,
            CASE
                WHEN is_duplicated = 0 THEN sm.product_qty
                WHEN sm.whs_id IS NOT NULL AND sm.whd_id IS NOT NULL
                    AND sm.whs_id != sm.whd_id THEN sm.product_qty
                ELSE 0
            END,
            CASE
                WHEN is_duplicated = 0 THEN sm.quantity
                WHEN sm.whs_id IS NOT NULL AND sm.whd_id IS NOT NULL
                    AND sm.whs_id != sm.whd_id THEN sm.quantity
                ELSE 0
            END,
            sm.date, sm.state, sm.company_id,
            CASE WHEN is_duplicated = 0 THEN sm.whs_id END,
            CASE
                WHEN is_duplicated = 0 AND NOT (
                    sm.whs_id IS NOT NULL AND sm.whd_id IS NOT NULL
                    AND sm.whs_id != sm.whd_id) THEN sm.whd_id
                WHEN is_duplicated = 1 AND (
                    sm.whs_id IS NOT NULL AND sm.whd_id IS NOT NULL
                    AND sm.whs_id != sm.whd_id) THEN sm.whd_id
            END
        FROM
            GENERATE_SERIES(0, 1, 1) is_duplicated,
            existing_sm sm
    )
SELECT
    MIN(id) as id,
    product_id,
    product_tmpl_id,
    lot_id,
    state,
    date,
    sum(product_qty) as product_qty,
    company_id,
    warehouse_id
FROM (SELECT
        m.id,
        m.product_id,
        m.tmpl_id as product_tmpl_id,
        m.lot_id,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN 'out'
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN 'in'
        END AS state,
        m.date::date AS date,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN -m.product_qty
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN m.product_qty
        END AS product_qty,
        m.company_id,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN m.whs_id
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN m.whd_id
        END AS warehouse_id
    FROM
        all_sm m
    WHERE
        m.product_qty != 0 AND
        m.state != 'done'
    UNION ALL
    SELECT
        -q.id as id,
        q.product_id,
        pp.product_tmpl_id,
        q.lot_id,
        'forecast' as state,
        date.*::date,
        q.quantity as product_qty,
        q.company_id,
        wh.id as warehouse_id
    FROM
        GENERATE_SERIES(
            (now() at time zone 'utc')::date - interval '%(report_period)s month',
            (now() at time zone 'utc')::date + interval '%(report_period)s month',
            '1 day'::interval) date,
        stock_quant q
    LEFT JOIN stock_location l on (l.id=q.location_id)
    LEFT JOIN stock_warehouse wh
        ON l.parent_path like concat('%%/', wh.view_location_id, '/%%')
    LEFT JOIN product_product pp on pp.id=q.product_id
    WHERE
        (l.usage = 'internal' AND wh.id IS NOT NULL) OR
        l.usage = 'transit'
    UNION ALL
    SELECT
        m.id,
        m.product_id,
        m.tmpl_id as product_tmpl_id,
        m.lot_id,
        'forecast' as state,
        GENERATE_SERIES(
        CASE
            WHEN m.state = 'done' THEN
                (now() at time zone 'utc')::date - interval '%(report_period)s month'
            ELSE GREATEST(m.date::date,
                (now() at time zone 'utc')::date - interval '%(report_period)s month')
        END,
        CASE
            WHEN m.state != 'done' THEN
                (now() at time zone 'utc')::date + interval '%(report_period)s month'
            ELSE m.date::date - interval '1 day'
        END, '1 day'::interval)::date date,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL AND m.state = 'done'
                THEN m.quantity
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL AND m.state = 'done'
                THEN -m.quantity
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN -m.product_qty
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN m.product_qty
        END AS product_qty,
        m.company_id,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN m.whs_id
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN m.whd_id
        END AS warehouse_id
    FROM
        all_sm m
    WHERE
        m.product_qty != 0 OR (m.state = 'done' AND m.quantity != 0)) AS forecast_qty
GROUP BY product_id, product_tmpl_id, lot_id, state, date, company_id, warehouse_id
);
"""
        report_period = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("stock.report_stock_quantity_period", default="3")
        )
        self.env.cr.execute(query, {"report_period": int(report_period)})
