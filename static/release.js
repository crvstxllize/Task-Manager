// Only a successful pair of responses can replace a confirmed release.
(() => {
  const panel = document.querySelector(".release");
  const number = document.querySelector(".masthead .release-number");
  const revision = panel.querySelector(".revision");
  const health = panel.querySelector(".health");
  const message = panel.querySelector(".update-message");
  const storageKey = "devops-task-manager:confirmed-release";
  let known = null;
  let timer;
  let current;
  let effectTimer;
  let formRevision = panel.querySelector(".revision code")?.textContent;

  function valid(build) {
    return build && typeof build.version === "string" && build.version.trim() &&
      (build.git_sha === null || /^[a-f0-9]{40}$/.test(build.git_sha));
  }

  function display(build) {
    number.textContent = build.version;
    number.setAttribute("aria-label", "Версия " + build.version);
    if (build.git_sha) {
      const code = document.createElement("code");
      code.textContent = build.git_sha.slice(0, 7);
      revision.replaceChildren(code);
    } else {
      revision.textContent = "Локальная сборка";
    }
  }

  try {
    const cached = JSON.parse(localStorage.getItem(storageKey));
    if (valid(cached)) {
      known = cached;
      display(known);
    }
  } catch { /* Storage may be unavailable. Keep tracking this tab in memory. */ }

  async function json(url, signal) {
    const response = await fetch(url, {cache: "no-store", signal});
    if (response.status !== 200) throw new Error("HTTP " + response.status);
    return response.json();
  }

  function confirm(build) {
    const changed = known?.git_sha && build.git_sha && known.git_sha !== build.git_sha;
    if (changed) {
      const byVersion = known.version !== build.version;
      message.textContent = "Обновлено с " + (byVersion ? known.version : known.git_sha.slice(0, 7)) +
        " до " + (byVersion ? build.version : build.git_sha.slice(0, 7));
      clearTimeout(effectTimer);
      panel.classList.remove("updating");
      void panel.offsetWidth;
      panel.classList.add("updating");
      effectTimer = setTimeout(() => panel.classList.remove("updating"), 920);
    } else if (!known || known.git_sha !== build.git_sha) {
      message.textContent = "";
    }
    if (!known || known.git_sha !== build.git_sha || known.version !== build.version) display(build);
    known = build;
    try { localStorage.setItem(storageKey, JSON.stringify(build)); } catch { /* memory fallback */ }
    health.dataset.state = "online";
    if (health.textContent !== "Сервис доступен") health.textContent = "Сервис доступен";
  }

  // A new Flask process may sign sessions with a new key. Refresh the forms
  // without replacing the task draft or replaying a write.
  async function refreshTokens(build, signal) {
    const short = build.git_sha?.slice(0, 7);
    if (!short || formRevision === short) return;
    const response = await fetch("/", {cache: "no-store", signal});
    if (!response.ok) return;
    const page = new DOMParser().parseFromString(await response.text(), "text/html");
    const token = page.querySelector('input[name="csrf_token"]')?.value;
    if (!token || signal.aborted) return;
    document.querySelectorAll('input[name="csrf_token"]').forEach(input => { input.value = token; });
    formRevision = short;
  }

  async function poll() {
    clearTimeout(timer);
    current?.abort();
    if (document.hidden) return;
    const controller = new AbortController();
    current = controller;
    const timeout = setTimeout(() => controller.abort(), 4000);
    try {
      const [status, build] = await Promise.all([
        json(health.href, controller.signal), json(revision.href, controller.signal)
      ]);
      if (status.status !== "ok" || !valid(build)) throw new Error("Invalid release response");
      if (current === controller && !document.hidden) {
        confirm(build);
        await refreshTokens(build, controller.signal);
      }
    } catch {
      if (current === controller && !document.hidden) {
        health.dataset.state = "offline";
        if (health.textContent !== "Связь потеряна") health.textContent = "Связь потеряна";
      }
    } finally {
      clearTimeout(timeout);
      if (current === controller && !document.hidden) timer = setTimeout(poll, 5000);
    }
  }

  document.addEventListener("visibilitychange", poll);
  window.addEventListener("pageshow", poll);
})();
