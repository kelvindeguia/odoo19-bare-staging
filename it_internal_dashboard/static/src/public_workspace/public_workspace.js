/** @odoo-module **/

import { Component, mount, onMounted, onWillStart, onWillUnmount, useState, whenReady } from "@odoo/owl";
import { getTemplate } from "@web/core/templates";

import { Dashboard } from "../summarized_dashboard/it_internal_dashboard_template";
import { HelpdeskDashboard } from "../helpdesk_dashboard/helpdesk_dashboard_template";
import { InfraDashboard } from "../infra_dashboard/infra_dashboard_template";
import { DevOpsDashboard } from "../devops_dashboard/devops_dashboard_template";
import { ComplianceDashboard } from "../compliance_dashboard/compliance_dashboard_template";
import { ManagementDashboard } from "../management_dashboard/management_dashboard_template";

export class PublicWorkspace extends Component {
    static template = "it_internal_dashboard.PublicWorkspace";
    static components = {
        Dashboard,
        HelpdeskDashboard,
        InfraDashboard,
        DevOpsDashboard,
        ComplianceDashboard,
        ManagementDashboard,
    };

    setup() {
        const root = document.getElementById("public_dashboard_root");
        this.token = root?.dataset?.token || "";
        this.weekLabel = root?.dataset?.week || "";
        const reportWindow = this.getReportWindow(new Date());

        this.state = useState({
            loading: true,
            nav: [],
            activeSection: null,
            sectionData: {},
            sectionLoading: false,
            error: null,

            showDateMenu: false,
            start_date: reportWindow.start,
            end_date: reportWindow.end,
            dateLabel: this.formatDateLabel(reportWindow.start, reportWindow.end),
            dateRangeError: null,
        });

        onWillStart(async () => {
            await this.loadNavigation();
        });

        onMounted(() => {
            document.body.classList.add("public_dashboard_active");
            this.onWindowHashChanged = () => {
                const section = this.getSectionFromLocation();
                if (section && section !== this.state.activeSection && this.hasSection(section)) {
                    this.selectSection(section, { updateUrl: false });
                }
            };
            window.addEventListener("hashchange", this.onWindowHashChanged);
        });

        onWillUnmount(() => {
            document.body.classList.remove("public_dashboard_active");
            if (this.onWindowHashChanged) {
                window.removeEventListener("hashchange", this.onWindowHashChanged);
            }
        });
    }

    getReportWindow(anchorDate) {
        const anchor = new Date(anchorDate);
        anchor.setHours(12, 0, 0, 0);
        const monday = new Date(anchor);
        monday.setDate(anchor.getDate() - ((anchor.getDay() + 6) % 7));
        const nextThursday = new Date(monday);
        nextThursday.setDate(monday.getDate() + 10);
        return {
            start: this.toISODate(monday),
            end: this.toISODate(nextThursday),
        };
    }

    toISODate(date) {
        const value = new Date(date);
        value.setHours(12, 0, 0, 0);
        return value.toISOString().slice(0, 10);
    }

    formatDateLabel(start, end) {
        const fmt = (d) =>
            new Date(d).toLocaleDateString(undefined, {
                month: "short",
                day: "2-digit",
                year: "numeric",
            });
        return `${fmt(start)} → ${fmt(end)}`;
    }

    async post(path, params = {}) {
        const response = await fetch(path, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params,
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        if (payload.error) {
            throw new Error(payload.error.data?.message || payload.error.message || "Server error");
        }
        return payload.result;
    }

    async loadNavigation() {
        try {
            const result = await this.post(`/it-internal-dashboard-test2/${encodeURIComponent(this.token)}/nav`);
            this.state.nav = result.nav || [];
            this.weekLabel = result.week_label || this.weekLabel;
            if (result.default_start_date && result.default_end_date) {
                this.state.start_date = result.default_start_date;
                this.state.end_date = result.default_end_date;
                this.state.dateLabel = this.formatDateLabel(result.default_start_date, result.default_end_date);
            }
            this.state.loading = false;

            const requestedSection = this.getSectionFromLocation();
            const firstSection = this.hasSection(requestedSection)
                ? requestedSection
                : this.state.nav[0]?.key;
            if (firstSection) {
                await this.selectSection(firstSection, { updateUrl: Boolean(requestedSection) });
            }
        } catch (error) {
            console.error("Public dashboard navigation failed:", error);
            this.state.loading = false;
            this.state.error = "Unable to load dashboard. The link may be invalid or expired.";
        }
    }

    toggleDateMenu() {
        this.state.showDateMenu = !this.state.showDateMenu;
    }

    async selectThisWeek() {
        await this.applyReportWindow(new Date());
    }

    async selectLastWeek() {
        const today = new Date();
        today.setDate(today.getDate() - 7);
        await this.applyReportWindow(today);
    }

    async selectThisMonth() {
        const today = new Date();
        const first = new Date(today.getFullYear(), today.getMonth(), 1);
        await this.applyReportWindow(first);
    }

    async selectLastMonth() {
        const today = new Date();
        const first = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        await this.applyReportWindow(first);
    }

    async selectLast30Days() {
        const today = new Date();
        const first = new Date(today);
        first.setDate(today.getDate() - 29);
        await this.applyDateRange(this.toISODate(first), this.toISODate(today));
    }

    async applyCustomRange() {
        await this.applyDateRange(this.state.start_date, this.state.end_date);
    }

    async applyReportWindow(anchorDate) {
        const reportWindow = this.getReportWindow(anchorDate);
        await this.applyDateRange(reportWindow.start, reportWindow.end);
    }

    async applyDateRange(start, end) {
        this.state.start_date = start;
        this.state.end_date = end;
        this.state.dateLabel = this.formatDateLabel(start, end);
        this.state.showDateMenu = false;

        this.state.sectionData = {};

        await this.refreshCurrentSection();
    }

    async refreshCurrentSection() {
        if (!this.state.activeSection) {
            return;
        }
        this.state.sectionLoading = true;
        try {
            await this.loadSectionData(this.state.activeSection, {
                start_date: this.state.start_date,
                end_date: this.state.end_date,
            });
        } catch (error) {
            console.error(`Public dashboard section ${this.state.activeSection} refresh failed:`, error);
            this.state.sectionData[this.state.activeSection] = { error: true };
        } finally {
            this.state.sectionLoading = false;
        }
    }

    async selectSection(key, options = {}) {
        if (!key || (this.state.activeSection === key && this.state.sectionData[key])) {
            return;
        }
        if (!this.hasSection(key)) {
            return;
        }

        this.state.activeSection = key;
        if (options.updateUrl !== false) {
            this.updateUrlSection(key);
        }
        if (this.state.sectionData[key]) {
            return;
        }

        this.state.sectionLoading = true;
        try {
            await this.loadSectionData(key, {
                start_date: this.state.start_date,
                end_date: this.state.end_date,
            });
        } catch (error) {
            console.error(`Public dashboard section ${key} failed:`, error);
            this.state.sectionData[key] = { error: true };
        } finally {
            this.state.sectionLoading = false;
        }
    }

    async loadSectionData(section, params = {}) {
        const data = await this.post(
            `/it-internal-dashboard-test2/${encodeURIComponent(this.token)}/data`,
            { section, ...params }
        );
        if (data?.error === "invalid_date_range") {
            this.state.dateRangeError =
                "That date range isn't available for this link. Try a shorter or more recent range.";
        } else if (data?.error) {
            // Other errors (not_found, section_required, etc.) aren't date-related —
            // don't show the date-range message for them, but don't leave a stale
            // one showing either.
            this.state.dateRangeError = null;
        } else {
            this.state.dateRangeError = null;
        }
        this.state.sectionData[section] = data;
        return data;
    }

    async loadPublicData(params = {}) {
        if (!this.state.activeSection) {
            return {};
        }
        this.state.sectionLoading = true;
        try {
            return await this.loadSectionData(this.state.activeSection, {
                start_date: this.state.start_date,
                end_date: this.state.end_date,
                ...params,
            });
        } finally {
            this.state.sectionLoading = false;
        }
    }

    get currentData() {
        return this.state.sectionData[this.state.activeSection] || null;
    }

    hasSection(key) {
        return Boolean(key && this.state.nav.some((section) => section.key === key));
    }

    getSectionFromLocation() {
        const hashSection = window.location.hash.replace(/^#/, "");
        if (hashSection) {
            return hashSection;
        }
        return new URLSearchParams(window.location.search).get("section");
    }

    updateUrlSection(key) {
        if (window.location.hash === `#${key}`) {
            return;
        }
        history.replaceState(null, "", `${window.location.pathname}${window.location.search}#${key}`);
    }

}

whenReady(() => {
    const root = document.getElementById("public_dashboard_root");
    if (root) {
        const loading = document.getElementById("public_dashboard_loading");
        loading?.remove();
        mount(PublicWorkspace, root, { getTemplate });
    }
});
