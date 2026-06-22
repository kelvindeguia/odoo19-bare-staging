/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { onMounted, onPatched } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Modern renderer used only for Workable list views.
 *
 * It keeps the standard Odoo list behavior intact and only adds:
 * - dashboard-style summary cards above the table
 * - modern row/header CSS hooks
 * - status/badge styling hooks
 * - full dashboard counters based on the complete current Odoo domain, not only visible rows
 */
class WorkableModernListRenderer extends ListRenderer {
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

        const profile = this._getListProfile(table);
        const cacheKey = this._getStatsCacheKey(profile.key);
        const cachedStats = this._statsCache.get(cacheKey);
        const stats = cachedStats || this._getPlaceholderStats(table, profile.key);

        this._renderDashboard(dashboard, profile, stats);

        if (!cachedStats) {
            this._loadDashboardStats(profile.key, cacheKey, dashboard, profile, table);
        }
    }

    _renderDashboard(dashboard, profile, stats) {
        dashboard.innerHTML = `
            <div class="o_workable_list_hero">
                <div class="o_workable_list_hero_text">
                    <span class="o_workable_list_kicker">Workable ATS</span>
                    <h2>${profile.title}</h2>
                    <p>${profile.subtitle}</p>
                </div>
                <div class="o_workable_list_hero_badge">
                    <i class="fa ${profile.icon}" aria-hidden="true"></i>
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

    _getStatsCacheKey(profileKey) {
        return JSON.stringify({
            model: this._getResModel(profileKey),
            profileKey,
            domain: this._getCurrentDomain(),
            count: this._getTotalRecordCount(0),
        });
    }

    _getResModel(profileKey) {
        const fromList = this.props?.list?.resModel || this.props?.list?.model?.root?.resModel || this.props?.resModel;
        if (fromList) {
            return fromList;
        }
        const modelByProfile = {
            departments: "workable.department",
            jobs: "workable.job",
            employees: "workable.employees",
            hiring_plans: "workable.hiring.plan",
            candidates: "workable.candidate",
        };
        return modelByProfile[profileKey];
    }

    _andDomain(baseDomain, extraDomain = []) {
        return [...(baseDomain || []), ...(extraDomain || [])];
    }

    async _searchCount(model, baseDomain, extraDomain = []) {
        return await this.orm.searchCount(model, this._andDomain(baseDomain, extraDomain));
    }

    async _loadDashboardStats(profileKey, cacheKey, dashboard, profile, table) {
        const requestSeq = ++this._dashboardRequestSeq;
        const model = this._getResModel(profileKey);
        if (!model || !this.orm) {
            return;
        }

        try {
            const baseDomain = this._getCurrentDomain();
            const total = await this._searchCount(model, baseDomain);
            let stats;

            if (profileKey === "candidates") {
                const [withEmail, sourced, webhookUpdated] = await Promise.all([
                    this._searchCount(model, baseDomain, [["email", "!=", false]]),
                    this._searchCount(model, baseDomain, [["sourced", "=", true]]),
                    this._searchCount(model, baseDomain, [["last_sync_source", "=", "webhook"]]),
                ]);
                stats = this._candidateStats(total, withEmail, sourced, webhookUpdated);
            } else if (profileKey === "departments") {
                const [withParent, topLevel] = await Promise.all([
                    this._searchCount(model, baseDomain, [["parent_id", "!=", false]]),
                    this._searchCount(model, baseDomain, [["parent_id", "=", false]]),
                ]);
                stats = this._departmentStats(total, withParent, topLevel);
            } else if (profileKey === "jobs") {
                const [published, draft, flexible] = await Promise.all([
                    this._searchCount(model, baseDomain, [["state", "=", "published"]]),
                    this._searchCount(model, baseDomain, [["state", "=", "draft"]]),
                    this._searchCount(model, baseDomain, [["workplace_type", "in", ["remote", "hybrid"]]]),
                ]);
                stats = this._jobStats(total, published, draft, flexible);
            } else if (profileKey === "employees") {
                const [active, inactive, withEmail] = await Promise.all([
                    this._searchCount(model, baseDomain, [["state", "=", "active"]]),
                    this._searchCount(model, baseDomain, [["state", "=", "inactive"]]),
                    this._searchCount(model, baseDomain, ["|", ["work_email", "!=", false], ["personal_email", "!=", false]]),
                ]);
                stats = this._employeeStats(total, active, inactive, withEmail);
            } else {
                const [open, pending, closed] = await Promise.all([
                    this._searchCount(model, baseDomain, [["status", "in", ["open", "approved"]]]),
                    this._searchCount(model, baseDomain, [["status", "in", ["pending", "processing", "on_hold", "reserved"]]]),
                    this._searchCount(model, baseDomain, [["status", "in", ["closed", "filled", "cancelled", "rejected"]]]),
                ]);
                stats = this._hiringPlanStats(total, open, pending, closed);
            }

            if (requestSeq !== this._dashboardRequestSeq) {
                return;
            }

            this._statsCache.set(cacheKey, stats);
            if (dashboard.isConnected) {
                this._renderDashboard(dashboard, profile, stats);
            }
        } catch (error) {
            console.warn("Workable dashboard count failed; falling back to visible rows.", error);
            const fallbackStats = this._getVisibleRowStats(table, profileKey);
            this._statsCache.set(cacheKey, fallbackStats);
            if (dashboard.isConnected) {
                this._renderDashboard(dashboard, profile, fallbackStats);
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

    _getListProfile(table) {
        const listRoot = table.closest(".o_workable_list_view") || table;
        if (listRoot.classList.contains("o_workable_department_list")) {
            return {
                key: "departments",
                title: "Departments",
                subtitle: "Organized Workable department records with hierarchy and external IDs.",
                icon: "fa-sitemap",
            };
        }
        if (listRoot.classList.contains("o_workable_job_list")) {
            return {
                key: "jobs",
                title: "Jobs",
                subtitle: "Modern overview of synced Workable job postings and publishing status.",
                icon: "fa-briefcase",
            };
        }
        if (listRoot.classList.contains("o_workable_employee_list")) {
            return {
                key: "employees",
                title: "Employees",
                subtitle: "Employee records synchronized from Workable with role and contact visibility.",
                icon: "fa-users",
            };
        }
        if (listRoot.classList.contains("o_workable_candidate_list")) {
            return {
                key: "candidates",
                title: "Candidates",
                subtitle: "Candidate records synchronized from Workable with ATS stage, status, and profile visibility.",
                icon: "fa-user-circle-o",
            };
        }
        return {
            key: "hiring_plans",
            title: "Hiring Plans",
            subtitle: "Requisition and hiring-plan control center for Workable synchronization.",
            icon: "fa-calendar-check-o",
        };
    }

    _getPlaceholderStats(table, profileKey) {
        const total = this._getTotalRecordCount([...table.querySelectorAll("tbody tr.o_data_row")].length);
        const loading = "...";

        if (profileKey === "candidates") {
            return this._candidateStats(total, loading, loading, loading, "Loading full counts");
        }
        if (profileKey === "departments") {
            return this._departmentStats(total, loading, loading, "Loading full counts");
        }
        if (profileKey === "jobs") {
            return this._jobStats(total, loading, loading, loading, "Loading full counts");
        }
        if (profileKey === "employees") {
            return this._employeeStats(total, loading, loading, loading, "Loading full counts");
        }
        return this._hiringPlanStats(total, loading, loading, loading, "Loading full counts");
    }

    _getVisibleRowStats(table, profileKey) {
        const rows = [...table.querySelectorAll("tbody tr.o_data_row")];
        const rowTexts = rows.map((row) => row.textContent.toLowerCase());
        const countWhere = (patterns) => rowTexts.filter((text) => patterns.some((pattern) => text.includes(pattern))).length;
        const total = this._getTotalRecordCount(rows.length);

        if (profileKey === "candidates") {
            const withEmail = rowTexts.filter((text) => text.includes("@")).length;
            return this._candidateStats(total, withEmail, countWhere(["sourced", "true"]), countWhere(["webhook"]), "Visible fallback");
        }
        if (profileKey === "departments") {
            const withParent = countWhere(["parent"]);
            return this._departmentStats(total, withParent, Math.max(rows.length - withParent, 0), "Visible fallback");
        }
        if (profileKey === "jobs") {
            return this._jobStats(total, countWhere(["published"]), countWhere(["draft"]), countWhere(["remote", "hybrid"]), "Visible fallback");
        }
        if (profileKey === "employees") {
            const inactive = countWhere(["inactive"]);
            return this._employeeStats(total, Math.max(countWhere(["active"]) - inactive, 0), inactive, rowTexts.filter((text) => text.includes("@")).length, "Visible fallback");
        }
        return this._hiringPlanStats(
            total,
            countWhere(["open", "approved"]),
            countWhere(["pending", "processing", "on hold", "on_hold", "reserved"]),
            countWhere(["closed", "filled", "cancelled", "rejected"]),
            "Visible fallback"
        );
    }

    _candidateStats(total, withEmail, sourced, webhookUpdated, hint = "All matching records") {
        return {
            total,
            cards: [
                { value: total, label: "Total Candidates", hint, icon: "fa-user-circle-o", tone: "tone-primary" },
                { value: withEmail, label: "With Email", hint, icon: "fa-envelope-o", tone: "tone-success" },
                { value: sourced, label: "Sourced", hint, icon: "fa-bullhorn", tone: "tone-warning" },
                { value: webhookUpdated, label: "Webhook Updated", hint, icon: "fa-bolt", tone: "tone-purple" },
            ],
        };
    }

    _departmentStats(total, withParent, topLevel, hint = "All matching records") {
        return {
            total,
            cards: [
                { value: total, label: "Total Departments", hint, icon: "fa-sitemap", tone: "tone-primary" },
                { value: withParent, label: "With Parent", hint, icon: "fa-code-fork", tone: "tone-success" },
                { value: topLevel, label: "Top Level", hint, icon: "fa-building-o", tone: "tone-info" },
                { value: total, label: "Synced Records", hint: "Workable API records", icon: "fa-cloud", tone: "tone-purple" },
            ],
        };
    }

    _jobStats(total, published, draft, flexible, hint = "All matching records") {
        return {
            total,
            cards: [
                { value: total, label: "Total Jobs", hint, icon: "fa-briefcase", tone: "tone-primary" },
                { value: published, label: "Published", hint, icon: "fa-check-circle", tone: "tone-success" },
                { value: draft, label: "Draft", hint, icon: "fa-pencil-square-o", tone: "tone-warning" },
                { value: flexible, label: "Remote / Hybrid", hint, icon: "fa-globe", tone: "tone-purple" },
            ],
        };
    }

    _employeeStats(total, active, inactive, withEmail, hint = "All matching records") {
        return {
            total,
            cards: [
                { value: total, label: "Total Employees", hint, icon: "fa-users", tone: "tone-primary" },
                { value: active, label: "Active", hint, icon: "fa-check-circle", tone: "tone-success" },
                { value: inactive, label: "Inactive", hint, icon: "fa-ban", tone: "tone-warning" },
                { value: withEmail, label: "With Email", hint, icon: "fa-envelope-o", tone: "tone-purple" },
            ],
        };
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

registry.category("views").add("workable_modern_list", {
    ...listView,
    Renderer: WorkableModernListRenderer,
});
