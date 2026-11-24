(() => {
  const root = document.documentElement;
  const key = "devops-task-manager:theme";
  try {
    if (localStorage.getItem(key) === "light") root.dataset.theme = "light";
  } catch { /* The default dark theme also works without storage. */ }

  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const navigation = performance.getEntriesByType("navigation")[0];
  // A native form POST returns to / via 303. Animate a fresh visit or reload,
  // but keep that redirect and history traversal visually stable.
  if (!reduced.matches && location.pathname === "/" && navigation &&
      (navigation.type === "reload" || (navigation.type === "navigate" && !navigation.redirectCount))) {
    root.classList.add("dashboard-enter", "entry-prepaint");
    document.addEventListener("DOMContentLoaded", () => {
      requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove("entry-prepaint")));
    }, {once: true});
  }
  document.addEventListener("animationend", event => {
    if (event.animationName === "panel-enter" && event.target.matches(".project-panel")) {
      root.classList.remove("dashboard-enter");
    }
  });
  reduced.addEventListener("change", () => root.classList.remove("dashboard-enter"));

  document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("theme-toggle");
    button.setAttribute("aria-pressed", String(root.dataset.theme === "light"));
    button.hidden = false;
    let requested = root.dataset.theme === "light" ? "light" : "dark";
    let origin = button;
    let running = false;

    function apply(theme) {
      root.dataset.theme = theme;
      button.setAttribute("aria-pressed", String(theme === "light"));
      try { localStorage.setItem(key, theme); } catch { /* Tab-only preference. */ }
    }

    async function render() {
      if (running) return;
      running = true;
      try {
        // Collapse clicks during a reveal to the last requested theme.
        while ((root.dataset.theme || "dark") !== requested) {
          const theme = requested;
          if (reduced.matches) {
            apply(theme);
          } else if (typeof document.startViewTransition !== "function") {
            root.classList.add("theme-fade");
            apply(theme);
            await new Promise(resolve => setTimeout(resolve, 180));
            root.classList.remove("theme-fade");
          } else {
            const rect = origin.getBoundingClientRect();
            const x = rect.left + rect.width / 2;
            const y = rect.top + rect.height / 2;
            const radius = Math.ceil(Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y)));
            root.style.setProperty("--reveal-origin", x + "px " + y + "px");
            root.style.setProperty("--reveal-radius", radius + "px");
            root.classList.add("theme-reveal");
            try {
              const transition = document.startViewTransition(() => apply(theme));
              await transition.finished;
            } catch {
              apply(theme);
            } finally {
              root.classList.remove("theme-reveal");
              root.style.removeProperty("--reveal-origin");
              root.style.removeProperty("--reveal-radius");
            }
          }
        }
      } finally {
        running = false;
      }
    }

    button.addEventListener("click", event => {
      root.classList.remove("dashboard-enter");
      requested = requested === "light" ? "dark" : "light";
      origin = event.detail ? (event.target.closest("svg") || button)
        : button.querySelector(requested === "light" ? ".sun" : ".moon");
      render();
    });
  });
})();
