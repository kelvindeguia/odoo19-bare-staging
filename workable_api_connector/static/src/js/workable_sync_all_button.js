/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched } from "@odoo/owl";


class WorkableSyncProgressDialog extends Component {
    static template = "workable_api_connector.WorkableSyncProgressDialog";
    static components = { Dialog };

    static props = {
        close: Function,
        state: Object,
        startSync: Function,
        toggleReport: Function,
    };
}



class WorkableSyncAllListRenderer extends ListRenderer {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this._statsCache = new Map();
        this._dashboardRequestSeq = 0;
        onMounted(() => this._applyWorkableListUi());
        onPatched(() => this._applyWorkableListUi());
    }

    _applyWorkableListUi() {
        window.requestAnimationFrame(() => {
            const table = this.tableRef?.el;
            if (!table) {
                return;
            }

            table.classList.add("o_workable_modern_table");

            for (const [index, row] of table.querySelectorAll("tbody tr.o_data_row").entries()) {
                row.classList.add("o_workable_modern_row");
                row.dataset.workableRowIndex = String(index + 1);
            }

            for (const th of table.querySelectorAll("thead th")) {
                th.classList.add("o_workable_modern_header_cell");
            }

            for (const badge of table.querySelectorAll(".badge")) {
                badge.classList.add("o_workable_modern_badge");
            }

            this._ensureDashboard(table);
        });
    }

    _ensureDashboard(table) {
        const renderer = table.closest(".o_list_renderer") || table.parentElement;
        if (!renderer) {
            return;
        }

        let dashboard = renderer.querySelector(":scope > .o_workable_list_dashboard");
        if (!dashboard) {
            dashboard = document.createElement("div");
            dashboard.className = "o_workable_list_dashboard";
            renderer.prepend(dashboard);
        }

        const cacheKey = this._getStatsCacheKey();
        const cachedStats = this._statsCache.get(cacheKey);
        const stats = cachedStats || this._getPlaceholderStats(table);

        this._renderDashboard(dashboard, stats);

        if (!cachedStats) {
            this._loadDashboardStats(cacheKey, dashboard, table);
        }
    }

    _renderDashboard(dashboard, stats) {
        dashboard.innerHTML = `
            <div class="o_workable_list_hero">
                <div class="o_workable_list_hero_text">
                    <span class="o_workable_list_kicker">Workable ATS</span>
                    <h2>Hiring Plans</h2>
                    <p>Requisition and hiring-plan control center for Workable synchronization.</p>
                </div>
                <div class="o_workable_list_hero_badge">
                    <i class="fa fa-calendar-check-o" aria-hidden="true"></i>
                    <span>${stats.total} total records</span>
                </div>
            </div>
            <div class="o_workable_list_cards">
                ${stats.cards.map((card) => `
                    <div class="o_workable_list_card ${card.tone}">
                        <div class="o_workable_list_card_icon"><i class="fa ${card.icon}" aria-hidden="true"></i></div>
                        <div>
                            <div class="o_workable_list_card_value">${card.value}</div>
                            <div class="o_workable_list_card_label">${card.label}</div>
                            <div class="o_workable_list_card_hint">${card.hint}</div>
                        </div>
                    </div>
                `).join("")}
            </div>
        `;
    }

    _getCurrentDomain() {
        const list = this.props?.list;
        const domain = list?.domain || list?.model?.root?.domain || this.props?.domain || [];
        return Array.isArray(domain) ? domain : [];
    }

    _getStatsCacheKey() {
        return JSON.stringify({
            model: this._getResModel(),
            domain: this._getCurrentDomain(),
            count: this._getTotalRecordCount(0),
        });
    }

    _getResModel() {
        return this.props?.list?.resModel || this.props?.list?.model?.root?.resModel || this.props?.resModel || "workable.hiring.plan";
    }

    _andDomain(baseDomain, extraDomain = []) {
        return [...(baseDomain || []), ...(extraDomain || [])];
    }

    async _searchCount(model, baseDomain, extraDomain = []) {
        return await this.orm.searchCount(model, this._andDomain(baseDomain, extraDomain));
    }

    async _loadDashboardStats(cacheKey, dashboard, table) {
        const requestSeq = ++this._dashboardRequestSeq;
        const model = this._getResModel();
        if (!model || !this.orm) {
            return;
        }

        try {
            const baseDomain = this._getCurrentDomain();
            const [total, open, pending, closed] = await Promise.all([
                this._searchCount(model, baseDomain),
                this._searchCount(model, baseDomain, [["status", "in", ["open", "approved"]]]),
                this._searchCount(model, baseDomain, [["status", "in", ["pending", "processing", "on_hold", "reserved"]]]),
                this._searchCount(model, baseDomain, [["status", "in", ["closed", "filled", "cancelled", "rejected"]]]),
            ]);
            const stats = this._hiringPlanStats(total, open, pending, closed);

            if (requestSeq !== this._dashboardRequestSeq) {
                return;
            }

            this._statsCache.set(cacheKey, stats);
            if (dashboard.isConnected) {
                this._renderDashboard(dashboard, stats);
            }
        } catch (error) {
            console.warn("Workable hiring dashboard count failed; falling back to visible rows.", error);
            const fallbackStats = this._getVisibleRowStats(table);
            this._statsCache.set(cacheKey, fallbackStats);
            if (dashboard.isConnected) {
                this._renderDashboard(dashboard, fallbackStats);
            }
        }
    }

    _getTotalRecordCount(fallback = 0) {
        const list = this.props?.list;
        const candidates = [
            list?.count,
            list?.model?.root?.count,
            list?.model?.root?.resIds?.length,
        ];

        for (const value of candidates) {
            if (Number.isFinite(value) && value >= 0) {
                return value;
            }
        }
        return fallback;
    }

    _getPlaceholderStats(table) {
        const total = this._getTotalRecordCount([...table.querySelectorAll("tbody tr.o_data_row")].length);
        return this._hiringPlanStats(total, "...", "...", "...", "Loading full counts");
    }

    _getVisibleRowStats(table) {
        const rows = [...table.querySelectorAll("tbody tr.o_data_row")];
        const rowTexts = rows.map((row) => row.textContent.toLowerCase());
        const countWhere = (patterns) => rowTexts.filter((text) => patterns.some((pattern) => text.includes(pattern))).length;
        const total = this._getTotalRecordCount(rows.length);
        return this._hiringPlanStats(
            total,
            countWhere(["open", "approved"]),
            countWhere(["pending", "processing", "on hold", "on_hold", "reserved"]),
            countWhere(["closed", "filled", "cancelled", "rejected"]),
            "Visible fallback"
        );
    }

    _hiringPlanStats(total, open, pending, closed, hint = "All matching records") {
        return {
            total,
            cards: [
                { value: total, label: "Total Hiring Plans", hint, icon: "fa-calendar-check-o", tone: "tone-primary" },
                { value: open, label: "Open / Approved", hint, icon: "fa-check-circle", tone: "tone-success" },
                { value: pending, label: "In Progress", hint, icon: "fa-clock-o", tone: "tone-warning" },
                { value: closed, label: "Closed", hint, icon: "fa-archive", tone: "tone-purple" },
            ],
        };
    }

}

class WorkableSyncAllListController extends ListController {
    setup() {
        super.setup();

        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        this.syncState = useState({
            title: "Workable Sync",
            mode: "confirm",
            currentStep: "Ready to sync",
            message: "This will sync Departments first, then Jobs, then Hiring Plans and Employees.",
            progress: 0,
            status: "idle",
            logs: [],
            currentModel: "",
            currentPage: 0,
            currentBatchCount: 0,
            currentTotalFetched: 0,
            showReport: false,
            reportVisible: false,
            reportData: {},
        });
    }

    async onSyncAllFromWorkable() {
        console.log("Sync All Workable Data clicked");

        this.syncState.title = "Workable Sync";
        this.syncState.mode = "confirm";
        this.syncState.currentStep = "Ready to sync";
        this.syncState.message = "This will sync Departments first, then Jobs, then Hiring Plans and Employees.";
        this.syncState.progress = 0;
        this.syncState.status = "idle";
        this.syncState.logs = [];

        this.dialog.add(WorkableSyncProgressDialog, {
            state: this.syncState,
            startSync: async () => {
                await this._startWorkableSync();
            },
            toggleReport: () => {
                this.syncState.reportVisible = !this.syncState.reportVisible;
            },
        });
    }

    async _startWorkableSync() {
        this.syncState.mode = "progress";
        this.syncState.currentStep = "Starting";
        this.syncState.message = "Preparing Workable sync...";
        this.syncState.progress = 0;
        this.syncState.status = "running";
        this.syncState.logs = [];
        this.syncState.currentModel = "";
        this.syncState.currentPage = 0;
        this.syncState.currentBatchCount = 0;
        this.syncState.currentTotalFetched = 0;

        try {
            const startResult = await this.orm.call(
                "workable.sync.service",
                "action_start_sync_all_from_workable",
                []
            );

            const progressId = startResult.progress_id;

            if (!progressId) {
                throw new Error("No progress ID was returned by the server.");
            }

            await this._pollSyncProgress(progressId);

        } catch (error) {
            this.syncState.status = "failed";
            this.syncState.currentStep = "Failed";
            this.syncState.message = error.message || "Unknown error";

            this.notification.add("Sync failed: " + (error.message || "Unknown error"), {
                title: "Workable Sync Error",
                type: "danger",
            });
        }
    }

    async _pollSyncProgress(progressId) {
        let keepPolling = true;

        while (keepPolling) {
            const progressData = await this.orm.call(
                "workable.sync.service",
                "action_get_sync_progress",
                [progressId]
            );

            this.syncState.status = progressData.state;
            this.syncState.currentStep = progressData.current_step;
            this.syncState.progress = progressData.progress;
            this.syncState.message = progressData.message;

            this.syncState.currentModel = progressData.current_model;
            this.syncState.currentPage = progressData.current_page;
            this.syncState.currentBatchCount = progressData.current_batch_count;
            this.syncState.currentTotalFetched = progressData.current_total_fetched;

            this.syncState.showReport = progressData.show_report;
            this.syncState.reportData = progressData.report_data || {};

            if (progressData.logs) {
                this.syncState.logs = progressData.logs
                    .split("\n")
                    .filter((log) => log.trim() !== "");
            }

            if (progressData.state === "done") {
                keepPolling = false;

                this.notification.add("Workable sync completed successfully.", {
                    title: "Workable Sync",
                    type: "success",
                });

                await this.model.root.load();
                break;
            }

            if (progressData.state === "failed") {
                keepPolling = false;
                throw new Error(progressData.message || "Sync failed.");
            }

            await new Promise((resolve) => setTimeout(resolve, 1000));
        }
    }
}


WorkableSyncAllListController.template = "workable_api_connector.WorkableSyncAllListView";


const workableSyncAllListView = {
    ...listView,
    Controller: WorkableSyncAllListController,
    Renderer: WorkableSyncAllListRenderer,
};


registry.category("views").add("workable_sync_all_list", workableSyncAllListView);