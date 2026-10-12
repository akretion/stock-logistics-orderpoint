/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { SelectMenu } from "@web/core/select_menu/select_menu";
import { patch } from "@web/core/utils/patch";
import { StockForecasted } from "@stock/stock_forecasted/stock_forecasted";

patch(StockForecasted, {
    components: { ...StockForecasted.components, SelectMenu },
});

patch(StockForecasted.prototype, {
    get forecastLotChoices() {
        return [
            { value: null, label: _t("All lots") },
            { value: false, label: _t("No lot") },
            ...(this.docs.lots || []).map((lot) => ({
                value: lot.id,
                label: lot.name,
            })),
        ];
    },

    get forecastLotValue() {
        return this.context.lot_id ?? null;
    },

    get forecastLotLabel() {
        return this.forecastLotChoices.find(
            (choice) => choice.value === this.forecastLotValue
        )?.label;
    },

    async updateForecastLot(lotId) {
        if (this.forecastLotValue === lotId) {
            return;
        }
        // Explicit null also clears a lot inherited from the original action.
        this.context.lot_id = lotId;
        // These hints describe the originating orderpoint, not the newly selected lot.
        for (const key of [
            "lead_days_date",
            "qty_to_order",
            "visibility_days_date",
            "qty_to_order_with_visibility_days",
        ]) {
            delete this.context[key];
        }
        await this.reloadReport();
    },

    get graphDomain() {
        const domain = super.graphDomain;
        if (this.docs.lot_filter_enabled && this.forecastLotValue !== null) {
            domain.push(["lot_id", "=", this.forecastLotValue]);
        }
        return domain;
    },

    get forecastGraphModel() {
        return this.docs.lot_filter_enabled
            ? "report.stock.quantity.by.lot"
            : "report.stock.quantity";
    },

    get forecastGraphContext() {
        const context = { fill_temporal: false };
        if (this.docs.lot_filter_enabled) {
            context.graph_view_ref =
                "stock_orderpoint_by_lot.stock_quantity_by_lot_graph";
        }
        return context;
    },
});
