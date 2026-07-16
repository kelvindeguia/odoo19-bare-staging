/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ManagementDashboard extends Component {
    static template = "it_internal_dashboard_test2.ManagementDashboard";

    static props = {
        publicMode: { type: Boolean, optional: true },
        publicData: { type: Object, optional: true },
    };

    setup() {
        this.publicMode = Boolean(this.props?.publicMode);
        if (this.props.publicMode) {
            this.management = useState(
                Object.assign(
                    {
                        summary_start: "",
                        summary_end: "",
                        overall_it_health_rating: "",
                        happiness_satisfaction_rating: "",
                    },
                    this.props.publicData || {}
                )
            );
            return;
        }
        this.orm = this.publicMode ? null : useService("orm");
        this.action = this.publicMode ? null : useService("action");

        this.recordId = this.props?.action?.context?.active_id;
        this.viewMode = this.publicMode ? "readonly" : (this.props?.action?.context?.view_mode || "edit");

        const today = new Date();

        const monday = new Date(today);
        monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));

        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);

        //  live reactive state (onchange)
        this.management = useState({
            summary_start: monday.toISOString().slice(0, 10),
            summary_end: sunday.toISOString().slice(0, 10),
            overall_it_health_rating: "",
            happiness_satisfaction_rating: "",
        });

        onWillStart(async () => {
            if (this.publicMode) {
                Object.assign(this.management, this.props.publicData || {});
                return;
            }

            if (this.recordId) {
                const result = await this.orm.read(
                    "it.management.dashboard",
                    [this.recordId],
                    [
                        "summary_start",
                        "summary_end",
                        "overall_it_health_rating",
                        "happiness_satisfaction_rating",
                    ]
                );
                if (result.length) {
                    Object.assign(this.management, result[0]);
                }
            }
        });

        onMounted(() => {
            document.body.classList.add("management_dashboard_active");
            document.body.classList.add("it_dashboard_navbar_active");
        });
        onWillUnmount(() => {
            document.body.classList.remove("management_dashboard_active");
            document.body.classList.remove("it_dashboard_navbar_active");
        });
    }

    // live update on typing
    updateField(field, value, ev = null) {
        
        const numericFields = [];

        
        if (numericFields.includes(field)) {
            this.management[field] = value === "" ? "" : Number(value);
        } else {
            this.management[field] = value;  
        }

      
        if (ev?.target?.tagName === "TEXTAREA") {
            const el = ev.target;

            el.style.height = "auto";
            el.style.height = el.scrollHeight + "px";
        }

    }

    getHealthLabel(value) {
        const map = {
            "weak": "🔴 Weak",
            "strong": "🟢 Strong",
            "very strong": "🟢 Very Strong",
        };
        return map[value] || "-";
    }

    // save to backend, redirect to list
    
    async saveData() {
        if (this.publicMode) {
            return;
        }

        try {
            // create record in backend
            await this.orm.create("it.management.dashboard", [
                {
                    summary_start: this.management.summary_start,
                    summary_end: this.management.summary_end,
                    overall_it_health_rating: this.management.overall_it_health_rating,
                    happiness_satisfaction_rating: this.management.happiness_satisfaction_rating,
                }
            ]);

            // redirect to list
            await this.action.doAction("it_internal_dashboard_test2.action_management_dashboard");

        } catch (error) {
            console.error("Error saving management data:", error);
        }
    }

}

registry.category("actions").add("management_dashboard_live2", ManagementDashboard);
