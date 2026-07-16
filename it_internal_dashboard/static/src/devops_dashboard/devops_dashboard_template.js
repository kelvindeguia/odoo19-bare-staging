/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class DevOpsDashboard extends Component {
    static template = "it_internal_dashboard.DevOpsDashboard";

    static props = {
        publicMode: { type: Boolean, optional: true },
        publicData: { type: Object, optional: true },
    };

    setup() {
        this.publicMode = Boolean(this.props?.publicMode);
        if (this.props.publicMode) {
            this.devops = useState(
                Object.assign(
                    {
                        summary_start: "",
                        summary_end: "",
                        devops_ongoing_projects: 0,
                        sprint_tasks_completed: "",
                        issues_raised: 0,
                        system_uptime: "",
                        cloud_servers_uptime: "",
                        devops_key_wins: "",
                        devops_challenges: "",
                        validation: {},
                    },
                    this.props.publicData || {}
                )
            );
            return;
        }
        this.orm = this.publicMode ? null : useService("orm");
        this.action = this.publicMode ? null : useService("action");
        this.notification = this.publicMode ? null : useService("notification");

        this.recordId = this.props?.action?.context?.active_id;
        this.viewMode = this.publicMode ? "readonly" : (this.props?.action?.context?.view_mode || "edit");

        const today = new Date();

        const monday = new Date(today);
        monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));

        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);

        this.devops = useState({
            summary_start: monday.toISOString().slice(0, 10),
            summary_end: sunday.toISOString().slice(0, 10),
            
            devops_ongoing_projects: 0,
            sprint_tasks_completed: 0,
            issues_raised: 0,
            system_uptime: "",
            cloud_servers_uptime: "",
            devops_kpis_attainment: "",
            devops_key_wins:"",
            devops_challenges:"",
            devops_help_needed:"",

            validation: {
                system_uptime: "",
                cloud_servers_uptime: "",
            },
        });

         onWillStart(async () => {
            if (this.publicMode) {
                Object.assign(this.devops, this.props.publicData || {});
                return;
            }

            if (this.recordId) {
                const result = await this.orm.read(
                    "it.devops.dashboard",
                    [this.recordId],
                    [
                        "summary_start",
                        "summary_end",
                        "devops_ongoing_projects",
                        "sprint_tasks_completed",
                        "issues_raised",
                        "system_uptime",
                        "cloud_servers_uptime",
                        "devops_kpis_attainment",
                        "devops_key_wins",
                        "devops_challenges",
                        "devops_help_needed",
                    ]
                );
                if (result.length) {
                    Object.assign(this.devops, result[0]);
                }
            }
        });

         onMounted(() => {
            document.body.classList.add("devops_dashboard_active");
            document.body.classList.add("it_dashboard_navbar_active");
        })

        onWillUnmount(() => {
            document.body.classList.remove("devops_dashboard_active");
            document.body.classList.remove("it_dashboard_navbar_active");
        });
    }

    // live update on typing
    updateField(field, value, ev = null) {
        const stringFields = [
            "devops_kpis_attainment",
            "devops_key_wins",
            "devops_challenges",
            "devops_help_needed",
            "sprint_tasks_completed",
        ];

        const numericFields = [
            "devops_ongoing_projects",
            "issues_raised",
        ];

        const percentageFields = [
            "system_uptime",
            "cloud_servers_uptime",
        ];

        if (stringFields.includes(field)) {
            this.devops[field] = value;
        }
        else if (numericFields.includes(field)) {
            this.devops[field] =
                value === "" ? "" : Number(value);
        }
        else if (percentageFields.includes(field)) {
            this.devops[field] =
                this.validatePercentage(field, value);
        }
        else {
            this.devops[field] = value;
        }

        if (ev?.target?.tagName === "TEXTAREA") {
            const el = ev.target;

            el.style.height = "auto";
            el.style.height = el.scrollHeight + "px";
        }
    }

    validatePercentage(field, value) {
        this.devops.validation[field] = "";
        if (value === "") {
            return "";
        }

        const cleaned = value.trim();

        if (!/^[0-9]*\.?[0-9]*$/.test(cleaned)) {
            this.devops.validation[field] =
                "Please only input Numbers.";
            this.notification?.add(
                "Please only input Numbers.",
                {
                    title: "Invalid Input",
                    type: "warning",
                }
            );
            return this.devops[field];
        }

        const number = Number(cleaned);

        if (number > 100) {
            this.devops.validation[field] =
                "Maximum value is 100.";
            this.notification?.add(
                "Maximum value is 100.",
                {
                    title: "Invalid Input",
                    type: "warning",
                }
            );
            return 100;
        }
        return number;
    }

    // save to backend, redirect to list
    
    async saveData() {
        if (this.publicMode) {
            return;
        }

        try {
            // create record in backend
            await this.orm.create("it.devops.dashboard", [
                {
                    summary_start: this.devops.summary_start,
                    summary_end: this.devops.summary_end,
                    devops_ongoing_projects: parseInt(this.devops.devops_ongoing_projects) || 0,
                    sprint_tasks_completed: this.devops.sprint_tasks_completed,
                    issues_raised: parseInt(this.devops.issues_raised) || 0,
                    system_uptime: this.devops.system_uptime,
                    cloud_servers_uptime: this.devops.cloud_servers_uptime,
                    devops_kpis_attainment: this.devops.devops_kpis_attainment,
                    devops_key_wins: this.devops.devops_key_wins,
                    devops_challenges: this.devops.devops_challenges,
                    devops_help_needed: this.devops.devops_help_needed,
                }
            ]);

            // redirect to list
            await this.action.doAction("it_internal_dashboard.action_devops_dashboard");

        } catch (error) {
            console.error("Error saving DevOps data:", error);
        }
    }

}

registry.category("actions").add("devops_dashboard_live2", DevOpsDashboard);
