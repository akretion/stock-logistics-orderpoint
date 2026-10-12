/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {StockOrderpointListController} from "@stock/views/stock_orderpoint_list_controller";

patch(StockOrderpointListController.prototype, {
    async onClickOrder(force_to_max) {
        const resIds = await this.getSelectedResIds();
        const action = await this.model.orm.call(
            this.props.resModel,
            "action_replenish",
            [resIds],
            {
                context: this.props.context,
                force_to_max: force_to_max,
            }
        );
        const refresh = () =>
            this.actionService.doAction("stock.action_replenishment", {
                stackPosition: "replaceCurrentAction",
            });
        if (action) {
            if (action.type === "ir.actions.act_window" && action.target === "new") {
                // Opening a dialog resolves before it closes; refresh only on close.
                return this.actionService.doAction(action, {onClose: refresh});
            }
            await this.actionService.doAction(action);
        }
        return refresh();
    },

    async onClickOrderWithSupplier(force_to_max) {
        return this.onClickOrder(force_to_max);
    },
});
