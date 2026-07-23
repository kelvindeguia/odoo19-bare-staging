{
    "name": "Workable API Health Monitor",
    "summary": "Monitor multiple Workable API tokens and webhook subscriptions",
    "version": "19.0.1.1.0",
    "category": "Technical/Monitoring",
    "author": "iSupport Worldwide",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/workable_health_security.xml",
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/workable_api_account_views.xml",
        "views/workable_subscription_views.xml",
        "views/workable_webhook_event_views.xml",
        "views/workable_health_log_views.xml",
        "views/workable_health_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "workable_api_health_monitor/static/src/scss/workable_monitor.scss",
        ],
    },
    "application": True,
    "installable": True,
}
