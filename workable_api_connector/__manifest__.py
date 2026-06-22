# -*- coding: utf-8 -*-
{
    'name': 'Workable ATS Connector',
    'version': '19.0.1.0.0',
    'category': 'Workable/Connector',
    'summary': 'Unified Workable API Connector for Odoo 19: Employees, Jobs, Departments, Hiring Plans',
    'description': """
        Workable ATS API Integration for Odoo 19.
        Unified connector for Workable Employees, Jobs, Departments, and Hiring Plans.
    """,
    'author': 'Kelvin De Guia',
    'depends': [
        'base',
        'mail',
        'web',
    ],
    'data': [
        'security/security_views.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/workable_department_views.xml',
        'views/workable_job_views.xml',
        'views/workable_employee_views.xml',
        'views/workable_hiring_plan_views.xml',
        'views/workable_candidate_views.xml',
        'views/workable_webhook_event_views.xml',
        'data/workable_webhook_cron.xml',
        'data/workable_cron.xml',
        'views/menuitems.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'workable_api_connector/static/src/scss/workable_views.scss',
            'workable_api_connector/static/src/js/workable_modern_list.js',
            'workable_api_connector/static/src/js/workable_modern_form.js',
            'workable_api_connector/static/src/js/workable_sync_all_button.js',
            'workable_api_connector/static/src/xml/workable_sync_all_button.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}