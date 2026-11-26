const byId = id => document.getElementById(id);
const originName = source => source === "manual" ? "вручную" : "автоматически";
let selected, historyKey;
async function refresh() {
  const state = await (await fetch("/api/state")).json();
  byId("app").textContent = state.app ? "Приложение доступно · версия " + state.app.version : "Приложение недоступно";
  byId("revision").textContent = state.app?.git_sha || "";
  const ci = state.ci;
  byId("ci").textContent = [ci.message, ci.sha?.slice(0, 7), ci.updated && new Date(ci.updated).toLocaleTimeString()].filter(Boolean).join(" · ");
  byId("checks").textContent = Object.entries(ci.checks || {}).map(([name, result]) => (name === "ci.yml" ? "Flask CI-CD" : "Docker test deployment") + " — " + result).join("　");
  if (state.manual_sha) byId("deploy").textContent = "Развернуть " + state.manual_sha.slice(0,7);
  selected ??= state.runs[0]?.id;
  const key = JSON.stringify([selected, state.runs]);
  if (historyKey !== key) {
    const buttons = state.runs.map(run => {
      const b = document.createElement("button"), info = document.createElement("small");
      b.className = "run";
      b.setAttribute("aria-pressed", String(run.id === selected));
      b.textContent = "#" + run.id + " · " + run.stage;
      info.textContent = [new Date(run.created).toLocaleString(), originName(run.source), run.sha.slice(0,7)].join(" · ");
      b.append(info);
      b.onclick = () => { selected = run.id; };
      return b;
    });
    byId("runs").replaceChildren(...(buttons.length ? buttons : ["Запусков пока нет."]));
    historyKey = key;
  }
  if (selected) {
    const id = selected;
    const data = await (await fetch("/api/runs/" + id + "/log")).json();
    if (selected === id) {
      byId("selected").textContent = "Лог запуска #" + id;
      const log = byId("log");
      if (log.textContent !== data.log) {
        const follow = log.scrollHeight - log.clientHeight - log.scrollTop < 4;
        log.textContent = data.log || "Ожидание исполнителя…";
        if (follow) log.scrollTop = log.scrollHeight;
      }
    }
  }
}
byId("deploy").onclick = async event => {
  const b = event.currentTarget;
  b.disabled = true;
  try {
    byId("notice").textContent = "Проверяем SHA и результаты CI…";
    const res = await fetch("/api/deploy", {method:"POST",headers:{"X-Panel-Action":"deploy"}});
    const data = await res.json();
    if (!res.ok) throw Error(data.error);
    selected = data.id;
    byId("notice").textContent = "Запрос принят · запуск #" + data.id;
  } catch (e) { byId("notice").textContent = e.message; }
  finally { b.disabled = false; }
};
async function poll() {
  try { await refresh(); }
  catch { byId("app").textContent = "Нет связи с панелью"; }
  setTimeout(poll, 700);
}
poll();
