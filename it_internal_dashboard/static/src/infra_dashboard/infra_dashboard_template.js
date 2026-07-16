/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class InfraDashboard extends Component {
    static template = "it_internal_dashboard_test2.InfraDashboard";

    static props = {
        publicMode: { type: Boolean, optional: true },
        publicData: { type: Object, optional: true },
    };

    setup() {
        this.publicMode = Boolean(this.props?.publicMode);
        if (this.props.publicMode) {
            this.infra = useState(
                Object.assign(
                    {
                        summary_start: "",
                        summary_end: "",
                        infra_ongoing_projects: 0,
                        network_uptime: "",
                        server_uptime: "",
                        security_breach: "",
                        telephony_uptime: "",
                        internet_uptime: "",
                        infra_key_wins: "",
                        infra_challenges: "",
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

        //  live reactive state (onchange)
        this.infra = useState({
            summary_start: monday.toISOString().slice(0, 10),
            summary_end: sunday.toISOString().slice(0, 10),

            infra_ongoing_projects: 0,
            network_uptime: "",
            server_uptime: "",
            security_breach: "",
            telephony_uptime: "",
            internet_uptime: "",

            infra_kpis_attainment: "",
            infra_key_wins:"",
            infra_challenges:"",
            infra_help_needed:"",

            validation: {
                network_uptime: "",
                server_uptime: "",
                telephony_uptime: "",
                internet_uptime: "",
            },
        });

        onWillStart(async () => {
            if (this.publicMode) {
                Object.assign(this.infra, this.props.publicData || {});
                return;
            }

            if (this.recordId) {
                const result = await this.orm.read(
                    "it.infra.dashboard",
                    [this.recordId],
                    [
                        "summary_start",
                        "summary_end",
                        "infra_ongoing_projects",
                        "network_uptime",
                        "server_uptime",
                        "security_breach",
                        "telephony_uptime",
                        "internet_uptime",
                        "infra_kpis_attainment",
                        "infra_key_wins",
                        "infra_challenges",
                        "infra_help_needed",
                    ]
                );

                if (result.length) {
                    Object.assign(this.infra, result[0]); 
                }
            }
        });
        onMounted(() => {
            document.body.classList.add("infra_dashboard_active");
            document.body.classList.add("it_dashboard_navbar_active");
        });
        onWillUnmount(() => {
            document.body.classList.remove("infra_dashboard_active");
            document.body.classList.remove("it_dashboard_navbar_active");
        });
    }

    // live update on typing
    updateField(field, value, ev = null) {
        const stringFields = [
            "infra_kpis_attainment",
            "infra_key_wins",
            "infra_challenges",
            "infra_help_needed",
        ]

        const numericFields = [
            "infra_ongoing_projects"
        ];

        const percentageFields = [
            "network_uptime",
            "server_uptime",
            "telephony_uptime",
            "internet_uptime",
        ];

        if (stringFields.includes(field)) {
            this.infra[field] = value;
        } else if (numericFields.includes(field)) {
            this.infra[field] = value === "" ? "" : Number(value);
        } else if (percentageFields.includes(field)) {
            this.infra[field] = this.validatePercentage(field, value);
        }else {
            this.infra[field] = value;
        }

        if (ev?.target?.tagName === "TEXTAREA") {
            const el = ev.target;

            el.style.height = "auto";
            el.style.height = el.scrollHeight + "px";
        }

    }

    validatePercentage(field, value) {
        this.infra.validation[field] = "";
        if (value === "") {
            return "";
        }
        const cleaned = value.trim();
        if (!/^[0-9]*\.?[0-9]*$/.test(cleaned)) {
            this.infra.validation[field] =
                "Please only input Numbers.";
            this.notification?.add(
                "Please only input Numbers.",
                {
                    title: "Invalid Input",
                    type: "warning",
                }
            );
            return this.infra[field];
        }
        const number = Number(cleaned);
        if (number > 100) {
            this.infra.validation[field] =
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
            await this.orm.create("it.infra.dashboard", [
                {
                    summary_start: this.infra.summary_start,
                    summary_end: this.infra.summary_end,

                    infra_ongoing_projects: parseInt(this.infra.infra_ongoing_projects) || 0,
                    network_uptime: this.infra.network_uptime,
                    server_uptime: this.infra.server_uptime,
                    security_breach: this.infra.security_breach,
                    telephony_uptime: this.infra.telephony_uptime,
                    internet_uptime: this.infra.internet_uptime,

                    infra_kpis_attainment: this.infra.infra_kpis_attainment,
                    infra_key_wins: this.infra.infra_key_wins,
                    infra_challenges: this.infra.infra_challenges,
                    infra_help_needed: this.infra.infra_help_needed,
                }
            ]);

            // redirect to list
            await this.action.doAction("it_internal_dashboard_test2.action_infra_dashboard");

        } catch (error) {
            console.error("Error saving infra data:", error);
        }
    }

}

registry.category("actions").add("infra_dashboard_live2", InfraDashboard);
