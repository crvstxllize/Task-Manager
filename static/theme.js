(() => {
  const root = document.documentElement;
  const key = root.dataset.themeKey || "devops-task-manager:theme";
  try {
    if (localStorage.getItem(key) === "light") root.dataset.theme = "light";
  } catch { /* The default dark theme also works without storage. */ }

  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const navigation = performance.getEntriesByType("navigation")[0];
  // A native form POST returns to / via 303. Animate a fresh visit or reload,
  // but keep that redirect and history traversal visually stable.
  if (root.hasAttribute("data-dashboard") && !reduced.matches && location.pathname === "/" && navigation &&
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

    // Load the isolated layer's stylesheet before the first interaction.
    const preview = document.createElement("div");
    preview.className = "theme-preview";
    preview.inert = true;
    const shadow = preview.attachShadow?.({mode: "open"});
    const canReveal = shadow && typeof preview.getAnimations === "function" &&
      CSS.supports("clip-path", "circle(0px at 0px 0px)");
    const content = document.createElement("div");
    const styles = [...document.querySelectorAll('link[rel="stylesheet"]')];
    const loaded = canReveal && Promise.all(styles.map(style => new Promise(resolve => {
      const link = style.cloneNode();
      link.onload = () => resolve(true);
      link.onerror = () => resolve(false);
      shadow.append(link);
    }))).then(results => results.every(Boolean));
    if (canReveal) {
      shadow.append(content);
      root.append(preview);
    }

    async function revealPreview(theme) {
      try {
        if (!reduced.matches) {
          if (root.classList.contains("entry-prepaint")) {
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
          }
          preview.dataset.theme = theme;
          const copy = document.body.cloneNode(true);
          copy.querySelector("#theme-toggle").setAttribute("aria-pressed", String(theme === "light"));
          content.classList.toggle("dashboard-enter", root.classList.contains("dashboard-enter"));
          content.replaceChildren(copy);
          preview.scrollTop = window.scrollY;
          for (const scroller of copy.querySelectorAll("[data-theme-scroll]")) {
            const original = document.getElementById(scroller.id);
            scroller.scrollTop = original.scrollTop;
            scroller.scrollLeft = original.scrollLeft;
          }

          // Match the entry transforms as well as the rotation of the artwork.
          // A panel whose entrance already finished must stay at its final position.
          const moving = ".ambient i, .orbit i, .core, .masthead, .release, .stat-card, .tasks, .progress-panel, .project-panel, .deploy-panel";
          const originals = document.body.querySelectorAll(moving);
          const copies = copy.querySelectorAll(moving);
          const pending = [];
          copies.forEach((element, index) => {
            const sources = originals[index].getAnimations();
            for (const target of element.getAnimations()) {
              const source = sources.find(item => item.animationName === target.animationName);
              if (!source) target.cancel();
              else if (source.startTime != null) target.startTime = source.startTime;
              else pending.push(source.ready.then(() => {
                if (source.startTime != null) target.startTime = source.startTime;
              }));
            }
          });
          if (pending.length) await Promise.allSettled(pending);
          preview.classList.add("revealing");
          const animation = preview.getAnimations().find(item => item.animationName === "theme-circle");
          if (animation) await animation.finished.catch(() => {});
        }
      } finally {
        apply(theme);
        preview.classList.remove("revealing");
        content.replaceChildren();
      }
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
          } else if (!canReveal || !await loaded) {
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
            try {
              await revealPreview(theme);
            } finally {
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
      requested = requested === "light" ? "dark" : "light";
      origin = event.detail ? (event.target.closest("svg") || button)
        : button.querySelector(requested === "light" ? ".sun" : ".moon");
      render();
    });
  });
})();
