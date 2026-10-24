(function () {
    "use strict";

    var body = document.body;
    var toggle = document.querySelector("[data-sidebar-toggle]");
    var overlay = document.querySelector("[data-sidebar-overlay]");
    var closeButtons = document.querySelectorAll("[data-sidebar-close]");

    function setSidebar(open) {
        if (!body) return;
        body.classList.toggle("sidebar-open", open);
        if (toggle) {
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        }
    }

    if (toggle) {
        toggle.addEventListener("click", function () {
            setSidebar(!body.classList.contains("sidebar-open"));
        });
    }

    if (overlay) {
        overlay.addEventListener("click", function () {
            setSidebar(false);
        });
    }

    closeButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            setSidebar(false);
        });
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            setSidebar(false);
        }
    });

    window.addEventListener("resize", function () {
        if (window.innerWidth > 900) {
            setSidebar(false);
        }
    });

    document.querySelectorAll("[data-toast]").forEach(function (toast) {
        var close = toast.querySelector("[data-toast-dismiss]");
        var hide = function () {
            toast.classList.add("is-hiding");
            window.setTimeout(function () {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 200);
        };
        if (close) {
            close.addEventListener("click", hide);
        }
        window.setTimeout(hide, 7000);
    });

    document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
        button.addEventListener("click", function () {
            var field = button.parentElement.querySelector("input");
            if (!field) return;
            var show = field.type === "password";
            field.type = show ? "text" : "password";
            button.textContent = show ? "Hide" : "Show";
            button.setAttribute("aria-label", show ? "Hide password" : "Show password");
        });
    });

    document.querySelectorAll("[data-file-drop] input[type=file]").forEach(function (input) {
        var nameTarget = input.closest("[data-file-drop]");
        var label = nameTarget ? nameTarget.querySelector("[data-file-name]") : null;
        input.addEventListener("change", function () {
            if (!label) return;
            label.textContent = input.files && input.files.length
                ? input.files[0].name
                : "PDF, images, logs, and documents — max 10 MB";
        });
    });
})();
