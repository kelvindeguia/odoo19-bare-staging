/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ComplianceDashboard extends Component {
    static template = "it_internal_dashboard.ComplianceDashboard";

    static props = {
        publicMode: { type: Boolean, optional: true },
        publicData: { type: Object, optional: true },
    };

    setup() {
        this.publicMode = Boolean(this.props?.publicMode);

        this.complianceOptions = useState([]);
        this.compliance = useState(this.defaultComplianceState());

        if (this.publicMode) {
            Object.assign(this.compliance, this.props.publicData || {});
            return;
        }

        this.orm = useService("orm");
        this.action = useService("action");

        this.recordId = this.props?.action?.context?.active_id;
        this.viewMode = this.props?.action?.context?.view_mode || "edit";

        onWillStart(async () => {
            await this.loadComplianceOptions();
            if (this.recordId) {
                await this.loadDashboardRecord();
            }
            this.syncSelectedCompliances();
        });

        onMounted(() => {
            document.body.classList.add("compliance_dashboard_active");
            document.body.classList.add("it_dashboard_navbar_active");
        });

        onWillUnmount(() => {
            document.body.classList.remove("compliance_dashboard_active");
            document.body.classList.remove("it_dashboard_navbar_active");
        });
    }

    defaultComplianceState() {
        const today = new Date();
        const monday = new Date(today);
        monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);

        return {
            summary_start: monday.toISOString().slice(0, 10),
            summary_end: sunday.toISOString().slice(0, 10),
            active_compliances: 0,
            compliances: [],
            compliance_status: [],
            compliance_progress: [],
            current_compliance_stage: [],
            pci_scanning_activities: "",
            audit_findings: "",
            it_risk_assessment_overview: "",
        };
    }

    async loadComplianceOptions() {
        const records = await this.orm.searchRead(
            "it.active.compliance",
            [],
            ["name", "stage", "status", "progress"],
            { order: "name asc" }
        );
        this.complianceOptions.splice(0, this.complianceOptions.length, ...records);
    }

    async loadDashboardRecord() {
        const result = await this.orm.read(
            "it.compliance.dashboard",
            [this.recordId],
            [
                "summary_start",
                "summary_end",
                "active_compliances",
                "compliances",
                "compliance_status",
                "compliance_progress",
                "pci_scanning_activities",
                "audit_findings",
                "it_risk_assessment_overview",
            ]
        );
        if (result.length) {
            Object.assign(this.compliance, result[0]);
            this.compliance.compliances = this.normalizeIds(result[0].compliances);
            this.compliance.compliance_status = this.normalizeIds(result[0].current_compliance_stage);
            this.compliance.compliance_status = this.normalizeIds(result[0].compliance_status);
            this.compliance.compliance_progress = this.normalizeIds(result[0].compliance_progress);
        }
    }

    normalizeIds(value) {
        return Array.isArray(value) ? value.map((id) => Number(id)) : [];
    }

    get selectedComplianceRecords() {
        const selectedIds = new Set(this.compliance.compliances);
        return this.complianceOptions.filter((compliance) => selectedIds.has(compliance.id));
    }

    get selectedComplianceNames() {
        return this.selectedComplianceRecords.map((compliance) => compliance.name).join(", ") || "-";
    }

    getComplianceLabel(value) {
        const map = {
            "": "Select Current Stage",
            kickoff: "Kickoff/Planning",
            fieldwork: "Fieldwork/Evidence Gathering",
            audit: "Audit",
            reporting: "Reporting",
            certification: "Certification",
        };
        return map[value] || "-";
    }

    getPciActivityLabel(value) {
        const map = {
            "": "Select Activity",
            asv: "ASV metrics",
            iva: "IVA metrics",
            enpt: "ENPT metrics",
            intp: "INTP metrics",
        };
        return map[value] || "-";
    }

    isComplianceSelected(complianceId) {
        return this.compliance.compliances.includes(complianceId);
    }

    toggleCompliance(complianceId, checked) {
        const selectedIds = new Set(this.compliance.compliances);
        if (checked) {
            selectedIds.add(complianceId);
        } else {
            selectedIds.delete(complianceId);
        }
        this.compliance.compliances = [...selectedIds];
        this.syncSelectedCompliances();
    }

    syncSelectedCompliances() {
        const selectedIds = this.normalizeIds(this.compliance.compliances);
        this.compliance.compliances = selectedIds;
        this.compliance.compliance_status = selectedIds;
        this.compliance.compliance_progress = selectedIds;
        this.compliance.active_compliances = selectedIds.length;
    }

    updateField(field, value, ev = null) {
        this.compliance[field] = value;

        if (ev?.target?.tagName === "TEXTAREA") {
            const el = ev.target;
            el.style.height = "auto";
            el.style.height = `${el.scrollHeight}px`;
        }
    }

    m2mCommand(ids) {
        return [[6, 0, this.normalizeIds(ids)]];
    }

    async saveData() {
        if (this.publicMode) {
            return;
        }

        this.syncSelectedCompliances();

        try {
            await this.orm.create("it.compliance.dashboard", [
                {
                    summary_start: this.compliance.summary_start,
                    summary_end: this.compliance.summary_end,
                    compliances: this.m2mCommand(this.compliance.compliances),
                    compliance_status: this.m2mCommand(this.compliance.compliance_status),
                    compliance_progress: this.m2mCommand(this.compliance.compliance_progress),
                    pci_scanning_activities: this.compliance.pci_scanning_activities,
                    audit_findings: this.compliance.audit_findings,
                    it_risk_assessment_overview: this.compliance.it_risk_assessment_overview,
                },
            ]);

            await this.action.doAction("it_internal_dashboard.action_compliance_dashboard");
        
        } catch (error) {
            console.error("Error saving compliance data:", error);
        }
    }
}

registry.category("actions").add("compliance_dashboard_live2", ComplianceDashboard);