/** @odoo-module **/
const { Chart } = window;
import { registry } from "@web/core/registry";
import { Component, useState, useRef, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class HelpdeskDashboard extends Component {
    static template = "it_internal_dashboard.HelpdeskDashboard";

    static props = {
        publicMode: { type: Boolean, optional: true },
        publicData: { type: Object, optional: true },
    };

    setup() {
        this.publicMode = Boolean(this.props?.publicMode);

        if (this.props.publicMode) {
            // Public mode — populate state from props, skip all backend calls

            this.helpdesk = useState(
                Object.assign(
                    {
                        viewMode: "readonly",
                        summary_start: "",
                        summary_end: "",
                        helpdesk_ongoing_projects: null,
                        new_hires_prepared: "",
                        fallout: null,
                        neo_score: null,
                        neo_target: null,
                        csat: null,
                        csat_target: null,
                        ticket_kpi: null,
                        ticket_kpi_target: null,
                        frt_prob: "", frt_req: "",
                        ert_prob: "", ert_req: "",
                        rt_prob: "", rt_req: "",
                        sla_achieved: "",
                        happiness_ratings: "",
                        new_count: 0,
                        on_hold: 0,
                        closed: 0,
                        neo_date_1: "", neo_date_2: "", neo_date_3: "", neo_date_4: "",
                        neo_score_1: null, neo_score_2: null, neo_score_3: null, neo_score_4: null,
                        overall_neo_score: 0,
                        comments_1: "", comments_2: "", comments_3: "", comments_4: "",
                        ticket_incident_in_progress: null,
                        ticket_incident_on_hold: null,
                        ticket_incident_resolved: null,
                        ticket_request_in_progress: null,
                        ticket_request_on_hold: null,
                        ticket_request_resolved: null,
                        pc_preparation_onsite: null,
                        pc_preparation_wfh: null,
                        projected_pc_preparation_onsite: null,
                        projected_pc_preparation_wfh: null,
                        total_new_hires_actual: 0,
                        total_new_hires_projected: 0,
                        isupport: null, iswerk: null,
                        projected_isupport: null, projected_iswerk: null,
                        ticket_count: 0,
                        tickets_from_web: 0,
                        tickets_from_email: 0,
                        tickets_from_phone: 0,
                        first_response_time: "",
                        response_time: "",
                        resolution_time: "",
                        good_rating: 0,
                        okay_rating: 0,
                        bad_rating: 0,
                        new_tickets: 0,
                        on_hold_tickets: 0,
                        closed_tickets: 0,
                        backlog_tickets: 0,
                        helpdesk_key_wins: "",
                        helpdesk_challenges: "",
                        helpdesk_kpis_attainment: "",
                        helpdesk_help_needed: "",

                        imageModal: {
                            open: false,
                            kind: null,
                            url: null,

                            zoom: 1,

                            pan: {
                                x: 0,
                                y: 0,
                            },

                            dragging: false,

                            startPointer: {
                                x: 0,
                                y: 0,
                            },

                            startPan: {
                                x: 0,
                                y: 0,
                            },
                        },
                        validation: {
                            csat: "", csat_target: "",
                            ticket_kpi: "", ticket_kpi_target: "",
                        },
                    },
                    this.props.publicData || {}
                )
            );

            this.pcPrepChartRef = useRef("pcPrepChart");
            this.projectedChartRef = useRef("projectedChart");


            this.computeNeoScore();

            onMounted(() => {
                this.renderCharts();
                this.updateCharts();
            });

            return; 
        }
        this.orm =  useService("orm");
        this.action =  useService("action");
        this.notification =  useService("notification");
        
        this.pcPrepChartRef = useRef("pcPrepChart");
        this.projectedChartRef = useRef("projectedChart");

        const ctx = this.props?.action?.context || {};

        this.recordId = ctx.active_id || null;

        this.isExistingRecord = Boolean(ctx.active_id);

        const today = new Date();

        const monday = new Date(
            today.getFullYear(),
            today.getMonth(),
            today.getDate()
        );

        monday.setDate(
            monday.getDate()
            - ((monday.getDay() + 6) % 7)
        );

        const sunday = new Date(
            monday.getFullYear(),
            monday.getMonth(),
            monday.getDate()
        );

        sunday.setDate(
            sunday.getDate() + 6
        );

        const formatLocalDate = (date) => {
            const year = date.getFullYear();

            const month = String(
                date.getMonth() + 1
            ).padStart(2, "0");

            const day = String(
                date.getDate()
            ).padStart(2, "0");

            return `${year}-${month}-${day}`;
        };

        const weeklySummaryStart = formatLocalDate(
            monday
        );

        const weeklySummaryEnd = formatLocalDate(
            sunday
        );

        console.info(
            "[HelpdeskDashboard] weekly range",
            {
                weeklySummaryStart,
                weeklySummaryEnd,
            }
        );

        // live reactive state (onchange)
        this.helpdesk = useState({
            viewMode: "readonly",

            summary_start: weeklySummaryStart,

            summary_end: weeklySummaryEnd,

            helpdesk_ongoing_projects: null,
            new_hires_prepared: "",
            fallout: null,

            neo_score: null,
            neo_target: null,

            csat: null,
            csat_target: null,

            ticket_kpi: null,
            ticket_kpi_target: null,

            frt_prob: "",
            frt_req: "",

            ert_prob: "",
            ert_req: "",

            rt_prob: "",
            rt_req: "",

            sla_achieved: "",
            happiness_ratings: "",

            new_count: 0,
            on_hold: 0,
            closed: 0,

            ticket_count: 0,
            tickets_from_web: 0,
            tickets_from_email: 0,
            tickets_from_phone: 0,

            first_response_time: "",
            response_time: "",
            resolution_time: "",

            good_rating: 0,
            okay_rating: 0,
            bad_rating: 0,

            new_tickets: 0,
            on_hold_tickets: 0,
            closed_tickets: 0,
            backlog_tickets: 0,

            neo_date_1: "",
            neo_date_2: "",
            neo_date_3: "",
            neo_date_4: "",

            neo_score_1: null,
            neo_score_2: null,
            neo_score_3: null,
            neo_score_4: null,

            overall_neo_score: 0,

            comments_1: "",
            comments_2: "",
            comments_3: "",
            comments_4: "",

            pc_preparation_onsite: null,
            pc_preparation_wfh: null,
            projected_pc_preparation_onsite: null,
            projected_pc_preparation_wfh: null,

            ticket_incident_in_progress: null,
            ticket_incident_on_hold: null,
            ticket_incident_resolved: null,

            ticket_request_in_progress: null,
            ticket_request_on_hold: null,
            ticket_request_resolved: null,

            isupport: null,
            iswerk: null,
            total_new_hires_actual: 0,

            projected_isupport:null,
            projected_iswerk: null,
            total_new_hires_projected: null,

            helpdesk_kpis_attainment: "",
            helpdesk_key_wins:"",
            helpdesk_challenges:"",
            helpdesk_help_needed:"",

            imageModal: {
                open: false,
                kind: null,
                url: null,

                zoom: 1,

                pan: {
                    x: 0,
                    y: 0,
                },

                dragging: false,

                startPointer: {
                    x: 0,
                    y: 0,
                },

                startPan: {
                    x: 0,
                    y: 0,
                },
            },

            validation: {
                csat: "",
                csat_target: "",
                ticket_kpi: "",
                ticket_kpi_target: "",
            },
        });

        onWillStart(async () => {
            console.info(
                "[HelpdeskDashboard] onWillStart entered"
            );

            const isDashboardAdmin = await this.orm.call(
                "it.helpdesk.dashboard",
                "can_current_user_edit",
                []
            );

            console.info(
                "[HelpdeskDashboard] edit permission",
                {
                    isDashboardAdmin,
                    initialRecordId: this.recordId,
                    initialIsExistingRecord:
                        this.isExistingRecord,
                }
            );

            const weeklyDomain = [
                [
                    "summary_start",
                    "=",
                    this.helpdesk.summary_start,
                ],
                [
                    "summary_end",
                    "=",
                    this.helpdesk.summary_end,
                ],
            ];

            console.info(
                "[HelpdeskDashboard] weekly lookup",
                {
                    domain: weeklyDomain,
                    summaryStart:
                        this.helpdesk.summary_start,
                    summaryEnd:
                        this.helpdesk.summary_end,
                }
            );

            /*
             * Always resolve the current weekly record.
             *
             * A menu/client action may contain no active_id or may
             * contain stale action context. The dashboard itself is
             * weekly, so summary_start + summary_end are the canonical
             * record identity for this screen.
             */
            const weeklyRecordIds = await this.orm.search(
                "it.helpdesk.dashboard",
                weeklyDomain,
                {
                    limit: 1,
                    order: "id desc",
                }
            );

            console.info(
                "[HelpdeskDashboard] weekly lookup result",
                {
                    weeklyRecordIds,
                }
            );

            if (weeklyRecordIds.length) {
                this.recordId = weeklyRecordIds[0];
                this.isExistingRecord = true;
            } else {
                this.recordId = null;
                this.isExistingRecord = false;
                this.helpdesk.viewMode = "edit";

                console.warn(
                    "[HelpdeskDashboard] no weekly record found",
                    {
                        weeklyDomain,
                    }
                );

                return;
            }

            const fieldsToRead = [
                "summary_start",
                "summary_end",
                "helpdesk_ongoing_projects",
                "new_hires_prepared",
                "fallout",
                "neo_score",
                "neo_target",
                "csat",
                "csat_target",
                "ticket_kpi",
                "ticket_kpi_target",
                "frt_prob",
                "frt_req",
                "ert_prob",
                "ert_req",
                "rt_prob",
                "rt_req",
                "sla_achieved",
                "happiness_ratings",
                "new_count",
                "on_hold",
                "closed",
                "ticket_count",
                "tickets_from_web",
                "tickets_from_email",
                "tickets_from_phone",
                "first_response_time",
                "response_time",
                "resolution_time",
                "good_rating",
                "okay_rating",
                "bad_rating",
                "new_tickets",
                "on_hold_tickets",
                "closed_tickets",
                "backlog_tickets",
                "neo_date_1",
                "neo_date_2",
                "neo_date_3",
                "neo_date_4",
                "neo_score_1",
                "neo_score_2",
                "neo_score_3",
                "neo_score_4",
                "overall_neo_score",
                "comments_1",
                "comments_2",
                "comments_3",
                "comments_4",
                "pc_preparation_onsite",
                "pc_preparation_wfh",
                "projected_pc_preparation_onsite",
                "projected_pc_preparation_wfh",
                "isupport",
                "iswerk",
                "total_new_hires_actual",
                "projected_isupport",
                "projected_iswerk",
                "total_new_hires_projected",
                "ticket_incident_in_progress",
                "ticket_incident_on_hold",
                "ticket_incident_resolved",
                "ticket_request_in_progress",
                "ticket_request_on_hold",
                "ticket_request_resolved",
                "helpdesk_kpis_attainment",
                "helpdesk_key_wins",
                "helpdesk_challenges",
                "helpdesk_help_needed",
            ];

            console.info(
                "[HelpdeskDashboard] reading weekly record",
                {
                    recordId: this.recordId,
                }
            );

            const result = await this.orm.read(
                "it.helpdesk.dashboard",
                [this.recordId],
                fieldsToRead
            );

            console.info(
                "[HelpdeskDashboard] weekly record payload",
                result
            );

            if (!result.length) {
                console.error(
                    "[HelpdeskDashboard] weekly record read empty",
                    {
                        recordId: this.recordId,
                    }
                );

                this.helpdesk.viewMode = "edit";
                return;
            }

            Object.assign(
                this.helpdesk,
                result[0]
            );

            this.helpdesk.viewMode =
                isDashboardAdmin
                    ? "edit"
                    : "readonly";

            this.computeNeoScore();

            console.info(
                "[HelpdeskDashboard] weekly state hydrated",
                {
                    recordId: this.recordId,
                    viewMode: this.helpdesk.viewMode,
                    ticketCount:
                        this.helpdesk.ticket_count,
                    web:
                        this.helpdesk.tickets_from_web,
                    email:
                        this.helpdesk.tickets_from_email,
                    phone:
                        this.helpdesk.tickets_from_phone,
                    newTickets:
                        this.helpdesk.new_tickets,
                    onHoldTickets:
                        this.helpdesk.on_hold_tickets,
                    closedTickets:
                        this.helpdesk.closed_tickets,
                    backlogTickets:
                        this.helpdesk.backlog_tickets,
                    goodRating:
                        this.helpdesk.good_rating,
                    okayRating:
                        this.helpdesk.okay_rating,
                    badRating:
                        this.helpdesk.bad_rating,
                }
            );
        });

        onMounted(() => {
            document.body.classList.add("helpdesk_dashboard_active");
            document.body.classList.add("it_dashboard_navbar_active");
            this._onKeydown = (ev) => {
                if (ev.key === "Escape" && this.helpdesk.imageModal.open) {
                    this.closeImageModal();
                }
            };

            window.addEventListener("keydown", this._onKeydown);
            this.renderCharts();
            this.updateCharts();
        });
        onWillUnmount(() => {
            document.body.classList.remove("helpdesk_dashboard_active");
            document.body.classList.remove("it_dashboard_navbar_active");
            window.removeEventListener("keydown", this._onKeydown);
        });
    }

    // live update on typing
    updateField(field, value, ev = null) {     
        this.helpdesk[field] = Number(value) || 0;
        const stringFields = [
            "new_hires_prepared",
            "frt_prob", "frt_req",
            "ert_prob", "ert_req",
            "rt_prob", "rt_req",
            "sla_achieved",
            "happiness_ratings",
            "comments_1",
            "comments_2",
            "comments_3",
            "comments_4",
            "helpdesk_kpis_attainment",
            "helpdesk_key_wins",
            "helpdesk_challenges",
            "helpdesk_help_needed",
            "neo_date_1",
            "neo_date_2",
            "neo_date_3",
            "neo_date_4"
        ];

        const numericFields = [
            "helpdesk_ongoing_projects",
            "fallout",
            "neo_score",
            "neo_target",
            "csat",
            "csat_target",
            "ticket_kpi",
            "ticket_kpi_target",
            "neo_score_1",
            "neo_score_2",
            "neo_score_3",
            "neo_score_4",
            "pc_preparation_onsite",
            "pc_preparation_wfh",
            "projected_pc_preparation_onsite",
            "projected_pc_preparation_wfh",
            "isupport",
            "iswerk",
            "projected_isupport",
            "projected_iswerk",
            "new_count",
            "on_hold",
            "closed",
            "ticket_incident_in_progress",
            "ticket_incident_on_hold",
            "ticket_incident_resolved",
            "ticket_request_in_progress",
            "ticket_request_on_hold",
            "ticket_request_resolved"
        ];
        
        if (stringFields.includes(field)) {
            this.helpdesk[field] = value;
        }else if (numericFields.includes(field)) {
            const percentageFields = [
                "csat",
                "csat_target",
                "ticket_kpi",
                "ticket_kpi_target",
            ];
            if (percentageFields.includes(field)) {
                this.helpdesk[field] =
                    this.validatePercentage(field, value);
            } else {
                this.helpdesk[field] =
                    value === "" ? null : Number(value);
            }
        }
        if (field.includes("neo_score_")) {
            this.computeNeoScore();
        }
        if (field === "isupport" || field === "iswerk") {
            this.helpdesk.total_new_hires_actual =
                (Number(this.helpdesk.isupport) || 0) +
                (Number(this.helpdesk.iswerk) || 0);
        }
        if (field === "projected_isupport" || field === "projected_iswerk") {
            this.helpdesk.total_new_hires_projected =
                (Number(this.helpdesk.projected_isupport) || 0) +
                (Number(this.helpdesk.projected_iswerk) || 0);
        }
        if (this._updateTimer) {
            clearTimeout(this._updateTimer);
        }
        this._updateTimer = setTimeout(() => {
            this.updateCharts();
        }, 150);
        if (ev?.target?.tagName === "TEXTAREA") {
            const el = ev.target;
            el.style.height = "auto";
            el.style.height = el.scrollHeight + "px";
        }
        if (ev?.target?.tagName === "TEXTAREA") {
            const el = ev.target;
            el.style.height = "auto";
            el.style.height = `${el.scrollHeight}px`;
        }
    }
    validatePercentage(field, value) {

        this.helpdesk.validation[field] = "";

        if (value === "") {
            return null;
        }
        if (!/^\d*\.?\d*$/.test(value)) {
            this.helpdesk.validation[field] =
                "Please only input Numbers.";
            this.notification?.add(
                "Please only input Numbers.",
                {
                    title: "Invalid Input",
                    type: "warning",
                }
            );
            return this.helpdesk[field];
        }
        const number = Number(value);
        if (number > 100) {
            this.helpdesk.validation[field] =
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


    renderCharts() {

        if (this.pcPrepChartRef.el) {
            this.chart1 = new Chart(this.pcPrepChartRef.el, {
                type: "bar",
                data: {
                    labels: ["Onsite", "WFH"],
                    datasets: [{
                        label: ["Completed"],
                        data: [
                            Number(this.helpdesk.isupport || 0),
                            Number(this.helpdesk.iswerk || 0),
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        }

        if (this.projectedChartRef.el) {
            this.chart2 = new Chart(this.projectedChartRef.el, {
                type: "bar",
                data: {
                    labels: ["Onsite", "WFH"],
                    datasets: [{
                        label: "Pending",
                        data: [
                            Number(this.helpdesk.projected_isupport || 0),
                            Number(this.helpdesk.projected_iswerk || 0),
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        }
    }

    updateCharts() {

       if (this.chart1) {
            this.chart1.data.datasets[0].data = [
                Number(this.helpdesk.isupport || 0),
                Number(this.helpdesk.iswerk || 0),
            ];

            this.chart1.update();
        }

        if (this.chart2) {
            this.chart2.data.datasets[0].data = [
                Number(this.helpdesk.projected_isupport || 0),
                Number(this.helpdesk.projected_iswerk || 0),
            ];

            this.chart2.update();
        }
    }

    computeNeoScore() {
        const scores = [
            this.helpdesk.neo_score_1,
            this.helpdesk.neo_score_2,
            this.helpdesk.neo_score_3,
            this.helpdesk.neo_score_4
        ].filter(v => v !== null && v !== "" && !isNaN(v));

        if (scores.length) {
            const total = scores.reduce((a, b) => a + Number(b), 0);
            this.helpdesk.overall_neo_score = (total / scores.length).toFixed(2);
        } else {
            this.helpdesk.overall_neo_score = 0;
        }
    }

  
    get pcPrepChartData() {
        return this.helpdesk.pc_prep_chart || {};
    }

    get projectedPcPrepChartData() {
        return this.helpdesk.projected_pc_prep_chart || {};
    }

    openImageModal(kind, url) {
        if (!url) return;
        this.helpdesk.imageModal.open = true;
        this.helpdesk.imageModal.kind = kind;
        this.helpdesk.imageModal.url = url;
        this.helpdesk.imageModal.zoom = 1;
        this.helpdesk.imageModal.pan = { x: 0, y: 0 };
    }

    closeImageModal() {
        this.helpdesk.imageModal.open = false;
        this.helpdesk.imageModal.kind = null;
        this.helpdesk.imageModal.url = null;
    }

    modalZoom(delta) {
        const modal = this.helpdesk.imageModal;
        modal.zoom = Math.min(5, Math.max(0.5, Number((modal.zoom + delta).toFixed(2))));
    }

    resetModalZoom() {
        this.helpdesk.imageModal.zoom = 1;
        this.helpdesk.imageModal.pan = { x: 0, y: 0 };
    }

    getModalImageStyle() {
        const { zoom, pan } = this.helpdesk.imageModal;
        return `transform: translate(${pan.x}px, ${pan.y}px) scale(${zoom}); transform-origin: center center;`;
    }

    onModalPointerDown(ev) {
        const modal = this.helpdesk.imageModal;
        modal.dragging = true;
        modal.startPointer = { x: ev.clientX, y: ev.clientY };
        modal.startPan = { ...modal.pan };
        ev.currentTarget.setPointerCapture(ev.pointerId);
    }

    onModalPointerMove(ev) {
        const modal = this.helpdesk.imageModal;
        if (!modal.dragging) return;
        const dx = ev.clientX - modal.startPointer.x;
        const dy = ev.clientY - modal.startPointer.y;
        modal.pan = { x: modal.startPan.x + dx, y: modal.startPan.y + dy };
    }

    onModalPointerUp(ev) {
        const modal = this.helpdesk.imageModal;
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

    triggerFile(ref) {
        ref?.el?.click();
    }

    editDashboard() {
        this.helpdesk.viewMode = "edit";

        console.info(
            "[HelpdeskDashboard] manual dashboard editing enabled",
            {
                recordId: this.recordId,
                viewMode: this.helpdesk.viewMode,
            }
        );
    }

    // save to backend, redirect to list
    async saveData() {
        if (this.publicMode) {
            return;
        }

        try {
            // create record in backend

                const values = {
                    summary_start: this.helpdesk.summary_start,
                    summary_end: this.helpdesk.summary_end,

                    helpdesk_ongoing_projects: this.helpdesk.helpdesk_ongoing_projects === null ? false : Number(this.helpdesk.helpdesk_ongoing_projects),

                    new_hires_prepared: this.helpdesk.new_hires_prepared === null ? false : Number(this.helpdesk.new_hires_prepared),
                    fallout: this.helpdesk.fallout === null ? false : Number(this.helpdesk.fallout),
                    neo_score: this.helpdesk.neo_score === null ? false : Number(this.helpdesk.neo_score),
                    neo_target: this.helpdesk.neo_target === null ? false : Number(this.helpdesk.neo_target),
                    csat:
                        this.helpdesk.csat,
                    csat_target:
                        this.helpdesk.csat_target,
                    ticket_kpi:
                        this.helpdesk.ticket_kpi,
                    ticket_kpi_target:
                        this.helpdesk.ticket_kpi_target,

                    frt_prob: this.helpdesk.frt_prob,
                    frt_req: this.helpdesk.frt_req,

                    ert_prob: this.helpdesk.ert_prob,
                    ert_req: this.helpdesk.ert_req,

                    rt_prob: this.helpdesk.rt_prob,
                    rt_req: this.helpdesk.rt_req,

                    sla_achieved: this.helpdesk.sla_achieved,
                    happiness_ratings: this.helpdesk.happiness_ratings,

                    new_count: parseInt(this.helpdesk.new_count) || 0,
                    on_hold: parseInt(this.helpdesk.on_hold) || 0,
                    closed: parseInt(this.helpdesk.closed) || 0,

                    neo_date_1: this.helpdesk.neo_date_1,
                    neo_date_2: this.helpdesk.neo_date_2,
                    neo_date_3: this.helpdesk.neo_date_3,
                    neo_date_4: this.helpdesk.neo_date_4,

                    neo_score_1: this.helpdesk.neo_score_1 === null ? false : Number(this.helpdesk.neo_score_1),
                    neo_score_2: this.helpdesk.neo_score_2 === null ? false : Number(this.helpdesk.neo_score_2),
                    neo_score_3: this.helpdesk.neo_score_3 === null ? false : Number(this.helpdesk.neo_score_3),
                    neo_score_4: this.helpdesk.neo_score_4 === null ? false : Number(this.helpdesk.neo_score_4),

                    overall_neo_score: parseFloat(this.helpdesk.overall_neo_score) || 0,

                    comments_1: this.helpdesk.comments_1,
                    comments_2: this.helpdesk.comments_2,
                    comments_3: this.helpdesk.comments_3,
                    comments_4: this.helpdesk.comments_4,

                    pc_preparation_onsite:
                        parseInt(this.helpdesk.pc_preparation_onsite) || 0,

                    pc_preparation_wfh:
                        parseInt(this.helpdesk.pc_preparation_wfh) || 0,

                    projected_pc_preparation_onsite:
                        parseInt(this.helpdesk.projected_pc_preparation_onsite) || 0,

                    projected_pc_preparation_wfh:
                        parseInt(this.helpdesk.projected_pc_preparation_wfh) || 0,

                    ticket_incident_in_progress:
                        parseInt(this.helpdesk.ticket_incident_in_progress) || 0,

                    ticket_incident_on_hold:
                        parseInt(this.helpdesk.ticket_incident_on_hold) || 0,

                    ticket_incident_resolved:
                        parseInt(this.helpdesk.ticket_incident_resolved) || 0,

                    ticket_request_in_progress:
                        parseInt(this.helpdesk.ticket_request_in_progress) || 0,

                    ticket_request_on_hold:
                        parseInt(this.helpdesk.ticket_request_on_hold) || 0,

                    ticket_request_resolved:
                        parseInt(this.helpdesk.ticket_request_resolved) || 0,

                    isupport: parseInt(this.helpdesk.isupport) || 0,
                    iswerk: parseInt(this.helpdesk.iswerk) || 0,

                    total_new_hires_actual:
                        parseInt(this.helpdesk.total_new_hires_actual) || 0,

                    projected_isupport:
                        parseInt(this.helpdesk.projected_isupport) || 0,

                    projected_iswerk:
                        parseInt(this.helpdesk.projected_iswerk) || 0,

                    total_new_hires_projected:
                        parseInt(this.helpdesk.total_new_hires_projected) || 0,

                    helpdesk_kpis_attainment:
                        this.helpdesk.helpdesk_kpis_attainment,

                    helpdesk_key_wins:
                        this.helpdesk.helpdesk_key_wins,

                    helpdesk_challenges:
                        this.helpdesk.helpdesk_challenges,

                    helpdesk_help_needed:
                        this.helpdesk.helpdesk_help_needed,
                };

                const existing = await this.orm.searchRead(
                "it.helpdesk.dashboard",
                [
                    ["summary_start", "=", values.summary_start],
                    ["summary_end", "=", values.summary_end],
                ],
                ["id"],
                {
                    limit: 1,
                    order: "id desc",
                }
            );

            if (existing.length) {

                this.recordId = existing[0].id;

                await this.orm.write(
                    "it.helpdesk.dashboard",
                    [this.recordId],
                    values,
                );

            }
            else {

                this.recordId = await this.orm.create(
                    "it.helpdesk.dashboard",
                    [values],
                );
                this.isExistingRecord = true;
                this.helpdesk.viewMode = "readonly";

                console.info(
                    "[HelpdeskDashboard] manual dashboard saved",
                    {
                        recordId: this.recordId,
                        viewMode: this.helpdesk.viewMode,
                    }
                );

            }
            // redirect to list
            await this.action.doAction("it_internal_dashboard.action_helpdesk_dashboard");

        } catch (error) {
            console.error("Error saving Helpdesk data:", error);
        }
    }
    
    downloadDashboard() {
        window.print(); 
    }
}

registry.category("actions").add("helpdesk_dashboard_live2", HelpdeskDashboard);
