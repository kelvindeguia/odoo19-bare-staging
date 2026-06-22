/** @odoo-module **/

/**
 * Workable modern form UI enhancer.
 *
 * Odoo-safe version:
 * - Does not register a custom form view key.
 * - Does not move existing Owl-managed DOM nodes.
 * - Does not use insertBefore on Odoo-rendered nodes.
 * - Adds only lightweight helper elements and CSS classes.
 */

const WORKABLE_FORM_SELECTOR = ".o_form_view";
const SWITCHER_CLASS = "o_workable_form_mode_switcher";
let observer = null;
let scanQueued = false;

function isElement(node) {
    return node instanceof Element;
}

function isWorkableForm(formRoot) {
    if (!isElement(formRoot)) {
        return false;
    }
    return Boolean(formRoot.querySelector(".o_workable_form_sheet"));
}

function getModelName(formRoot) {
    const modelFromData = formRoot.dataset?.model || formRoot.closest("[data-model]")?.dataset?.model;
    if (modelFromData) {
        return modelFromData;
    }
    const title = formRoot.querySelector(".o_workable_title_block .oe_title, .o_workable_title_block, .o_form_view_container")?.textContent;
    return (title || "workable_default").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_");
}

function getStorageKey(formRoot) {
    return `workable_form_mode_${getModelName(formRoot)}`;
}

function decorateHero(formRoot) {
    const sheet = formRoot.querySelector(".o_workable_form_sheet");
    const titleBlock = formRoot.querySelector(".o_workable_title_block");
    const quickInfo = formRoot.querySelector(".o_workable_quick_info");

    if (!isElement(sheet)) {
        return;
    }

    sheet.classList.add("o_workable_record_shell");

    if (isElement(titleBlock)) {
        titleBlock.classList.add("o_workable_record_header_card");

        if (!titleBlock.querySelector(".o_workable_record_toolbar")) {
            const toolbar = document.createElement("div");
            toolbar.className = "o_workable_record_toolbar";
            toolbar.innerHTML = `
                <span class="o_workable_record_pill"><i class="fa fa-circle" aria-hidden="true"></i> Workable Record</span>
                <span class="o_workable_record_pill muted"><i class="fa fa-cloud" aria-hidden="true"></i> Synced Data</span>
            `;
            titleBlock.prepend(toolbar);
        }
    }

    if (isElement(quickInfo)) {
        quickInfo.classList.add("o_workable_quick_info_card");
    }
}

function decorateNotebookPages(formRoot) {
    const notebook = formRoot.querySelector(".o_notebook");
    if (!isElement(notebook)) {
        return;
    }

    const tabs = [...notebook.querySelectorAll(".nav-tabs .nav-link")];
    const panes = [...notebook.querySelectorAll(".tab-content > .tab-pane")];

    panes.forEach((pane, index) => {
        if (!isElement(pane)) {
            return;
        }

        const title = tabs[index]?.textContent?.trim() || `Section ${index + 1}`;
        pane.classList.add("o_workable_onepage_section");
        pane.dataset.workablePageTitle = title;

        if (!pane.querySelector(".o_workable_onepage_section_header")) {
            const header = document.createElement("button");
            header.type = "button";
            header.className = "o_workable_onepage_section_header";
            header.innerHTML = `<span>${title}</span><i class="fa fa-chevron-up" aria-hidden="true"></i>`;
            header.addEventListener("click", (ev) => {
                if (!formRoot.classList.contains("o_workable_form_onepage_mode")) {
                    return;
                }
                ev.preventDefault();
                ev.stopPropagation();
                pane.classList.toggle("is-collapsed");
            });
            pane.prepend(header);
        }
    });
}

function decorateManualOnepageSections(formRoot) {
    const container = formRoot.querySelector(".o_workable_manual_onepage_container");
    if (!isElement(container)) {
        return;
    }

    for (const section of container.querySelectorAll(".o_workable_manual_onepage_section")) {
        if (!isElement(section) || section.dataset.workableManualReady === "1") {
            continue;
        }
        section.dataset.workableManualReady = "1";
        const header = section.querySelector(":scope > .o_workable_onepage_section_header");
        if (!isElement(header)) {
            continue;
        }
        header.setAttribute("role", "button");
        header.setAttribute("tabindex", "0");
        const toggleSection = (ev) => {
            if (!formRoot.classList.contains("o_workable_form_onepage_mode")) {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            section.classList.toggle("is-collapsed");
        };
        header.addEventListener("click", toggleSection);
        header.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter" || ev.key === " ") {
                toggleSection(ev);
            }
        });
    }
}

function setMode(formRoot, mode, persist = true) {
    const normalizedMode = mode === "onepage" ? "onepage" : "tabbed";

    formRoot.classList.toggle("o_workable_form_onepage_mode", normalizedMode === "onepage");
    formRoot.classList.toggle("o_workable_form_tabbed_mode", normalizedMode !== "onepage");

    for (const button of formRoot.querySelectorAll(".o_workable_mode_btn")) {
        const isActive = button.dataset.workableMode === normalizedMode;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
    }

    if (persist) {
        window.localStorage.setItem(getStorageKey(formRoot), normalizedMode);
    }
}

function ensureModeSwitcher(formRoot) {
    if (formRoot.querySelector(`.${SWITCHER_CLASS}`)) {
        return;
    }

    const sheet = formRoot.querySelector(".o_workable_form_sheet");
    if (!isElement(sheet)) {
        return;
    }

    const switcher = document.createElement("div");
    switcher.className = SWITCHER_CLASS;
    switcher.innerHTML = `
        <div class="o_workable_form_mode_text">
            <span class="o_workable_form_mode_label">View Options</span>
            <span class="o_workable_form_mode_hint">Choose Notebook for tabbed editing or One Page for a single scrollable record view.</span>
        </div>
        <div class="btn-group o_workable_form_mode_buttons" role="group" aria-label="Workable form layout switcher">
            <button type="button" class="btn btn-light o_workable_mode_btn" data-workable-mode="tabbed">
                <i class="fa fa-folder-open-o me-1"></i> Notebook
            </button>
            <button type="button" class="btn btn-light o_workable_mode_btn" data-workable-mode="onepage">
                <i class="fa fa-align-left me-1"></i> One Page
            </button>
        </div>
    `;

    switcher.addEventListener("click", (ev) => {
        const button = ev.target.closest("[data-workable-mode]");
        if (!button) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        setMode(formRoot, button.dataset.workableMode, true);
    });

    sheet.prepend(switcher);
}

function enhanceWorkableForm(formRoot) {
    if (!isWorkableForm(formRoot)) {
        return;
    }

    formRoot.classList.add("o_workable_modern_form_root");

    decorateHero(formRoot);
    decorateNotebookPages(formRoot);
    decorateManualOnepageSections(formRoot);
    ensureModeSwitcher(formRoot);

    const savedMode = window.localStorage.getItem(getStorageKey(formRoot)) || "tabbed";
    setMode(formRoot, savedMode, false);
}

function scanWorkableForms() {
    scanQueued = false;
    if (!document.body) {
        return;
    }

    for (const formRoot of document.querySelectorAll(WORKABLE_FORM_SELECTOR)) {
        enhanceWorkableForm(formRoot);
    }
}

function scheduleScan() {
    if (scanQueued) {
        return;
    }
    scanQueued = true;
    window.requestAnimationFrame(scanWorkableForms);
}

function startObserver() {
    if (!document.body) {
        window.setTimeout(startObserver, 50);
        return;
    }

    scheduleScan();

    if (!observer) {
        observer = new MutationObserver(scheduleScan);
        observer.observe(document.body, { childList: true, subtree: true });
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startObserver, { once: true });
} else {
    startObserver();
}
