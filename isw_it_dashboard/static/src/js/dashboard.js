/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ITDashboard extends Component {
    static template = "isw_it_dashboard.Dashboard";
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({loading: true, periods: 0, neo: 0, pc: 0, highlights: 0, projects: 0, latest: null});
        onWillStart(() => this.load());
    }
    async load() {
        const [periods, neo, pc, highlights, projects, latest] = await Promise.all([
            this.orm.searchCount("it.dashboard.period", []),
            this.orm.searchCount("it.neo.session", []),
            this.orm.searchCount("it.pc.preparation", []),
            this.orm.searchCount("it.department.highlight", []),
            this.orm.searchCount("it.project.update", []),
            this.orm.searchRead("it.dashboard.period", [], ["name", "date_from", "date_to", "state", "completion_percentage"], {limit: 1, order: "date_from desc"}),
        ]);
        Object.assign(this.state, {periods, neo, pc, highlights, projects, latest: latest[0] || null, loading: false});
    }
    open(xmlid) { this.action.doAction(xmlid); }
}
registry.category("actions").add("isw_it_dashboard.main", ITDashboard);
