{
    "name": "IT Internal Dashboard (With Zoho)",
    "description": "With Zoho Desk API Integration -- Unfinished",
    "version": "19.0.1.0.0",
    "author": "IT Internal",
    "license": "OPL-1",
    "depends": [
        "base",
        "web",
        "website"
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        'views/dashboard_menu.xml',
        'views/devops_dashboard_form_views.xml',
        'views/helpdesk_juniorit_dashboard_form_views.xml',
        'views/infra_dashboard_form_views.xml',
        'views/compliance_dashboard_form_views.xml',
        'views/management_dashboard_form_views.xml',
        'views/lighthouse_report_overview_forms.xml',
        'views/dashboard_summary_history_form_views.xml',
        'views/public_dashboard_templates.xml',
        'views/dashboard_publication_views.xml',
        'views/zoho_credentials_views.xml',
        'data/zoho_cron.xml',
    ],
    "assets": {
        "web.assets_backend": [         
        'it_internal_dashboard_test2/static/src/js/chart.js',

        'it_internal_dashboard_test2/static/src/summarized_dashboard/it_internal_dashboard_template.js',
        'it_internal_dashboard_test2/static/src/summarized_dashboard/it_internal_dashboard_template.xml',
        'it_internal_dashboard_test2/static/src/summarized_dashboard/it_internal_dashboard_template.scss',

        'it_internal_dashboard_test2/static/src/devops_dashboard/devops_dashboard_template.js',
        'it_internal_dashboard_test2/static/src/devops_dashboard/devops_dashboard_template.xml',
        'it_internal_dashboard_test2/static/src/devops_dashboard/devops_dashboard_template.scss',

        'it_internal_dashboard_test2/static/src/infra_dashboard/infra_dashboard_template.js',
        'it_internal_dashboard_test2/static/src/infra_dashboard/infra_dashboard_template.xml',
        'it_internal_dashboard_test2/static/src/infra_dashboard/infra_dashboard_template.scss',

        'it_internal_dashboard_test2/static/src/helpdesk_dashboard/helpdesk_dashboard_template.js',
        'it_internal_dashboard_test2/static/src/helpdesk_dashboard/helpdesk_dashboard_template.xml',
        'it_internal_dashboard_test2/static/src/helpdesk_dashboard/helpdesk_dashboard_template.scss',

        'it_internal_dashboard_test2/static/src/compliance_dashboard/compliance_dashboard_template.js',
        'it_internal_dashboard_test2/static/src/compliance_dashboard/compliance_dashboard_template.xml',
        'it_internal_dashboard_test2/static/src/compliance_dashboard/compliance_dashboard_template.scss',

        'it_internal_dashboard_test2/static/src/management_dashboard/management_dashboard_template.js',
        'it_internal_dashboard_test2/static/src/management_dashboard/management_dashboard_template.xml',
        'it_internal_dashboard_test2/static/src/management_dashboard/management_dashboard_template.scss',
        ],
        "web.assets_frontend": [
        'it_internal_dashboard_test2/static/src/js/chart.js',

        'it_internal_dashboard_test2/static/src/summarized_dashboard/it_internal_dashboard_template.js',
        'it_internal_dashboard_test2/static/src/summarized_dashboard/it_internal_dashboard_template.xml',
        'it_internal_dashboard_test2/static/src/summarized_dashboard/it_internal_dashboard_template.scss',

        'it_internal_dashboard_test2/static/src/devops_dashboard/devops_dashboard_template.js',
        'it_internal_dashboard_test2/static/src/devops_dashboard/devops_dashboard_template.xml',
        'it_internal_dashboard_test2/static/src/devops_dashboard/devops_dashboard_template.scss',

        'it_internal_dashboard_test2/static/src/infra_dashboard/infra_dashboard_template.js',
        'it_internal_dashboard_test2/static/src/infra_dashboard/infra_dashboard_template.xml',
        'it_internal_dashboard_test2/static/src/infra_dashboard/infra_dashboard_template.scss',

        'it_internal_dashboard_test2/static/src/helpdesk_dashboard/helpdesk_dashboard_template.js',
        'it_internal_dashboard_test2/static/src/helpdesk_dashboard/helpdesk_dashboard_template.xml',
        'it_internal_dashboard_test2/static/src/helpdesk_dashboard/helpdesk_dashboard_template.scss',

        'it_internal_dashboard_test2/static/src/compliance_dashboard/compliance_dashboard_template.js',
        'it_internal_dashboard_test2/static/src/compliance_dashboard/compliance_dashboard_template.xml',
        'it_internal_dashboard_test2/static/src/compliance_dashboard/compliance_dashboard_template.scss',

        'it_internal_dashboard_test2/static/src/management_dashboard/management_dashboard_template.js',
        'it_internal_dashboard_test2/static/src/management_dashboard/management_dashboard_template.xml',
        'it_internal_dashboard_test2/static/src/management_dashboard/management_dashboard_template.scss',

        'it_internal_dashboard_test2/static/src/public_workspace/public_workspace.js',
        'it_internal_dashboard_test2/static/src/public_workspace/public_workspace.xml',
        'it_internal_dashboard_test2/static/src/public_workspace/public_workspace.scss',
        ],
    },
    "application": True,
    "installable": True,
}

