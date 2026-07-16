/** @odoo-module **/

const { Chart } = window;

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export class Dashboard extends Component {
    static template = "it_internal_dashboard.Dashboard";

    setup() {
        this.publicMode = Boolean(this.props?.publicMode);
        const today = new Date();

        const reportWindow = this.getReportWindow(today);

        this.state = useState({
            showDateMenu: false,

            start_date: reportWindow.start,
            end_date: reportWindow.end,
            dateLabel: this.formatDateLabel(reportWindow.start, reportWindow.end),
            imageZoom: {
                lighthouse: 1,
                neo: 1,
            },
            imageModal: {
                open: false,
                kind: null,
                url: null,
                zoom: 1,
                pan: { x: 0, y: 0 },
                dragging: false,
                startPointer: { x: 0, y: 0 },
                startPan: { x: 0, y: 0 },
            },
            data: {
                summary: {},
                helpdesk_kpi_table: [],
                helpdesk_ticket_table: [],
                helpdesk_ticket_remarks: [],
                latest_helpdesk_reports: {
                    lighthouse_report_url: "",
                    neo_satisfaction_score_url: "",
                    summary_date: "",
                    new_tickets: 0,
                    on_hold_tickets: 0,
                    closed_tickets: 0,
                    backlog_tickets: 0
                },
                helpdesk_pc_prep: { actual: {}, projected: {} },

                active_compliances: 0,
                current_compliance_stage: "",
                overall_it_health_rating: "",

                complianceStage: "",
                itHealthRating: "",
                itHealthColorClass: "",
                activeCompliancesCount: 0,
            },
            loading: true,
        });
        this.charts = {};

        onWillStart(async () => {
            if (this.publicMode) {
                this.applyPublicData(this.props.publicData || {});
                this.state.loading = false;
            } else {
                await this.loadData(false);
            }
        });

        onMounted(async () => {
            document.body.classList.add("it_internal_dashboard_active");
            document.body.classList.add("it_dashboard_navbar_active");
            this._onKeydown = (ev) => {
                if (ev.key === "Escape" && this.state.imageModal.open) {
                    this.closeImageModal();
                }
            };
            window.addEventListener("keydown", this._onKeydown);
            await new Promise(requestAnimationFrame);
            await new Promise(requestAnimationFrame);
            this.renderChart();
        });

        onWillUnmount(() => {
            document.body.classList.remove("it_internal_dashboard_active");
            document.body.classList.remove("it_dashboard_navbar_active");
            window.removeEventListener("keydown", this._onKeydown);
            this.destroyCharts();
        });
    }

    async loadData(render = true) {
        if (this.publicMode) {
            if (this.props.loadPublicData) {
                const result = await this.props.loadPublicData({
                    start_date: this.state.start_date,
                    end_date: this.state.end_date,
                });
                this.applyPublicData(result || {});
            } else {
                this.applyPublicData(this.props.publicData || {});
            }
            this.state.loading = false;
            if (render) {
                await new Promise(requestAnimationFrame);
                this.renderChart();
            }
            return;
        }

        this.state.loading = true;
        try {
            const result = await rpc("/web/dataset/call_kw", {
                model: "it.dashboard.summary",
                method: "get_dashboard_data",
                args: [this.state.start_date, this.state.end_date],
                kwargs: {},
            });

            this.state.data = result;
            this.processCustomKpis(result);
        } catch (error) {
            console.error("Dashboard data load failed:", error);
        } finally {
            this.state.loading = false;
        }

        if (render) {
            await new Promise(requestAnimationFrame);
            this.renderChart();
        }
    }

    applyPublicData(data) {
        this.state.data = data || {};
        if (data?.start_date && data?.end_date) {
            this.state.start_date = data.start_date;
            this.state.end_date = data.end_date;
            this.state.dateLabel = this.formatDateLabel(data.start_date, data.end_date);
        }
        this.processCustomKpis(this.state.data || {});
    }

    async applyCustomRange() {
        await this.applyReportWindow(this.state.start_date);
    }

    async onDateRangeChanged(value) {
        await this.applyReportWindow(value.startDate);
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
        await this.applyReportWindow(first);
    }

    async applyReportWindow(anchorDate) {
        const reportWindow = this.getReportWindow(anchorDate);
        this.state.start_date = reportWindow.start;
        this.state.end_date = reportWindow.end;
        this.state.dateLabel = this.formatDateLabel(reportWindow.start, reportWindow.end);
        this.state.showDateMenu = false;
        await this.loadData();
    }

    getReportWindow(anchorDate) {
        const anchor = new Date(anchorDate);
        anchor.setHours(12, 0, 0, 0);
        const monday = new Date(anchor);
        monday.setDate(
            anchor.getDate() -
            ((anchor.getDay() + 6) % 7)
        );
        const sunday = new Date(monday);
        sunday.setDate(
            monday.getDate() + 6
        );

        return {
            start: this.toISODate(monday),
            end: this.toISODate(sunday),
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

    processCustomKpis(data) {
        this.state.data.complianceStage = data.current_compliance_stage || "N/A";
        this.state.data.activeCompliancesCount = data.active_compliances || 0;

        const health = data.overall_it_health_rating || "weak";

        this.state.data.itHealthRating = health.toUpperCase();

        if (health === "weak") {
            this.state.data.itHealthColorClass = "text-danger bg-danger-light";
        } else if (health === "strong") {
            this.state.data.itHealthColorClass = "text-success bg-success-light";
        } else if (health === "very strong") {
            this.state.data.itHealthColorClass = "text-primary bg-primary-light";
        } else {
            this.state.data.itHealthColorClass = "text-muted";
        }
    }


    get summary() {
        return this.state.data.summary || {};
    }

    get helpdeskKpiTable() {
        return this.state.data?.helpdesk_kpi_table || [];
    }

    get helpdeskTicketRemarks() {
        return this.state.data?.helpdesk_ticket_remarks || [];
    }

    get helpdeskTicketTable() {
        return this.state.data?.helpdesk_ticket_table || [];
    }

    get latestHelpdeskReports() {
        return (
            this.state.data?.latest_helpdesk_reports || {
                lighthouse_report_url: "",
                neo_satisfaction_score_url: "",
                summary_date: "",
                new_tickets: 0,
                on_hold_tickets: 0,
                closed_tickets: 0,
                backlog_tickets: 0
            }
        );
    }

    get helpdeskPcPrep() {
        return this.state.data?.helpdesk_pc_prep || {};
    }

    zoomReport(kind, delta) {
        const current = this.state.imageZoom[kind] || 1;
        this.state.imageZoom[kind] = Math.min(3, Math.max(0.5, Number((current + delta).toFixed(2))));
    }

    resetReportZoom(kind) {
        this.state.imageZoom[kind] = 1;
    }

    openImageModal(kind, url) {
        if (!url) return;
        this.state.imageModal.open = true;
        this.state.imageModal.kind = kind;
        this.state.imageModal.url = url;
        this.state.imageModal.zoom = 1;
        this.state.imageModal.pan = { x: 0, y: 0 };
    }

    closeImageModal() {
        this.state.imageModal.open = false;
        this.state.imageModal.kind = null;
        this.state.imageModal.url = null;
    }

    modalZoom(delta) {
        const modal = this.state.imageModal;
        modal.zoom = Math.min(5, Math.max(0.5, Number((modal.zoom + delta).toFixed(2))));
    }

    resetModalZoom() {
        this.state.imageModal.zoom = 1;
        this.state.imageModal.pan = { x: 0, y: 0 };
    }

    getModalImageStyle() {
        const { zoom, pan } = this.state.imageModal;
        return `transform: translate(${pan.x}px, ${pan.y}px) scale(${zoom}); transform-origin: center center;`;
    }

    onModalPointerDown(ev) {
        const modal = this.state.imageModal;
        modal.dragging = true;
        modal.startPointer = { x: ev.clientX, y: ev.clientY };
        modal.startPan = { ...modal.pan };
        ev.currentTarget.setPointerCapture(ev.pointerId);
    }

    onModalPointerMove(ev) {
        const modal = this.state.imageModal;
        if (!modal.dragging) return;
        const dx = ev.clientX - modal.startPointer.x;
        const dy = ev.clientY - modal.startPointer.y;
        modal.pan = { x: modal.startPan.x + dx, y: modal.startPan.y + dy };
    }

    onModalPointerUp(ev) {
        const modal = this.state.imageModal;
        modal.dragging = false;
        try {
            ev.currentTarget.releasePointerCapture(ev.pointerId);
        } catch (e) {
            // pointer capture may already be released
        }
    }

    onModalWheel(ev) {
        ev.preventDefault();
        this.modalZoom(ev.deltaY > 0 ? -0.1 : 0.1);
    }

    getReportZoomStyle(kind) {
        const zoom = this.state.imageZoom[kind] || 1;
        return `max-height: 320px; object-fit: contain; transform: scale(${zoom}); transform-origin: center center;`;
    }

    getKpiColorClass(value) {
        if (
            value === null ||
            value === undefined ||
            value === ""
        ) {
            return "";
        }

        const numericValue = Number(value);

        if (Number.isNaN(numericValue)) {
            return "";
        }

        return numericValue > 80
            ? "it_kpi_good"
            : "it_kpi_bad";
    }

    formatPercent(value) {
        if (
            value === null ||
            value === undefined ||
            value === ""
        ) {
            return "-";
        }

        return value;
    }
    
    renderChart() {
        if (!this.state.data) return;

        this.destroyCharts();

        const actualCanvas = document.getElementById("pc_prep_actual_chart");
        if (actualCanvas) {
            Chart.getChart(actualCanvas)?.destroy();
            this.charts.pcPrepActual = new Chart(actualCanvas, {
                type: "bar",
                data: this.helpdeskPcPrep.actual || {
                    labels: ["Onsite", "WFH"],
                    datasets: [{ label: "Completed", data: [0, 0], backgroundColor: ["#3b82f6", "#3b82f6"] }],
                },
                options: { responsive: true, scales: { y: { beginAtZero: true } } },
            });
        }

        const projectedCanvas = document.getElementById("pc_prep_projected_chart");
        if (projectedCanvas) {
            Chart.getChart(projectedCanvas)?.destroy();
            this.charts.pcPrepProjected = new Chart(projectedCanvas, {
                type: "bar",
                data: this.helpdeskPcPrep.projected || {
                    labels: ["Onsite", "WFH"],
                    datasets: [{ label: "Projected", data: [0, 0], backgroundColor: ["#f97316", "#f97316"] }],
                },
                options: { responsive: true, scales: { y: { beginAtZero: true } } },
            });
        }
    }

    destroyCharts() {
        Object.keys(this.charts).forEach((key) => {
            if (this.charts[key]) {
                this.charts[key].destroy();
            }
        });
        this.charts = {};
    }
}

registry.category("actions").add("it_internal_dashboard_live2", Dashboard);
