/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { GraphModel } from "@web/views/graph/graph_model";
import { StockForecastedGraphView } from "@stock/stock_forecasted/forecasted_graph";

export class StockForecastedByLotGraphModel extends GraphModel {
    _getDefaultFilterLabel(field) {
        return field.fieldName === "lot_id"
            ? _t("No lot")
            : super._getDefaultFilterLabel(field);
    }
}

registry.category("views").add("stock_forecasted_by_lot_graph", {
    ...StockForecastedGraphView,
    Model: StockForecastedByLotGraphModel,
});
