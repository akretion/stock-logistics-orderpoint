/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { StockOrderpointListController } from "@stock/views/stock_orderpoint_list_controller";

patch(StockOrderpointListController.prototype, {
    async onClickOrderWithSupplier(force_to_max) {
        const resIds = await this.getSelectedResIds();
        const action = await this.model.orm.call(this.props.resModel, 'action_replenish', [resIds], {
            context: this.props.context,
            force_to_max: force_to_max,
        });
        if (action) {
            const value = await this.actionService.doAction(action);
            if (
                action.type === "ir.actions.act_window" &&
                action.target === "new"
            ) {
                // Do not refresh/rerun the replenishment action.
                return value;
            }
        }
        return this.actionService.doAction('stock.action_replenishment', {
            stackPosition: 'replaceCurrentAction',
        });
    },
});
