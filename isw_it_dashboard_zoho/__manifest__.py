{
    "name": "ISW IT Dashboard - Zoho Desk Integration",
    "version": "19.0.1.3.0",
    "summary": "Synchronize Zoho Desk tickets into the ISW IT Dashboard",
    "category": "Operations/IT",
    "author": "ISW",
    "license": "LGPL-3",
    "depends": ["isw_it_dashboard"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/res_config_settings_views.xml",
        "views/zoho_ticket_views.xml",
        "views/sync_log_views.xml",
        "views/webhook_event_views.xml",
        "views/menu.xml"
    ],
    "installable": True
}
