// Forms remain ordinary POSTs when progressive enhancement is unavailable.
const list = document.querySelector("#task-list");
const input = document.querySelector("#task-title");
const error = document.querySelector("#form-error");
const feedback = document.querySelector("#feedback");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
let saving = false;

function motion(element, frames) {
  if (!element || reducedMotion.matches || !element.animate) return;
  return element.animate(frames, {duration: 200, easing: "ease-out"}).finished;
}

input.addEventListener("input", () => {
  error.textContent = "";
  input.removeAttribute("aria-invalid");
});

document.addEventListener("submit", async event => {
  const form = event.target;
  const adding = form.id === "add-task";
  if (!adding && !list.contains(form)) return;
  event.preventDefault();
  if (saving) return;

  const row = form.closest(".task-row");
  const actionError = row?.querySelector(".row-error") || error;
  const button = form.querySelector("button");
  const deleting = button.matches(".delete");
  const nextId = row?.nextElementSibling?.id || row?.previousElementSibling?.id;
  const oldIds = new Set([...list.children].map(item => item.id));
  const data = new FormData(form);
  const buttons = [...document.querySelectorAll("form button")];
  let focusTarget = button;
  saving = true;
  actionError.textContent = "";
  button.setAttribute("aria-busy", "true");
  buttons.forEach(item => { item.disabled = true; });
  if (adding) input.readOnly = true;
  feedback.textContent = "Сохранение…";

  try {
    const response = await fetch(form.action, {method: "POST", body: data});
    const page = new DOMParser().parseFromString(await response.text(), "text/html");
    if (!response.ok) {
      const validation = page.querySelector("#form-error")?.textContent.trim();
      if (adding && validation) {
        input.setAttribute("aria-invalid", "true");
        focusTarget = input;
      }
      throw new Error(validation || "Не удалось сохранить изменение. Обновите страницу и попробуйте ещё раз.");
    }
    const updated = page.querySelector("#task-list");
    if (!updated) throw new Error("Не удалось обновить список. Обновите страницу.");
    if (deleting) {
      await motion(row, [
        {height: row.offsetHeight + "px", minHeight: "0", overflow: "hidden", opacity: 1},
        {height: "0px", minHeight: "0", overflow: "hidden", opacity: 0}
      ]);
    }
    list.replaceChildren(...updated.children);
    const progress = document.querySelector("#task-progress");
    const savedProgress = page.querySelector("#task-progress");
    progress.max = savedProgress.max;
    progress.value = savedProgress.value;
    document.querySelectorAll("[data-stat], [data-summary]").forEach(counter => {
      const selector = counter.hasAttribute("data-stat")
        ? '[data-stat="' + counter.dataset.stat + '"]'
        : '[data-summary="' + counter.dataset.summary + '"]';
      const value = page.querySelector(selector).textContent;
      if (value !== counter.textContent) {
        counter.textContent = value;
        motion(counter, [{opacity: 0.3}, {opacity: 1}]);
      }
    });
    if (adding) {
      const created = [...list.children].find(item => !oldIds.has(item.id));
      if (created) motion(created, [
        {height: "0px", minHeight: "0", opacity: 0, overflow: "hidden"},
        {height: created.offsetHeight + "px", minHeight: "0", opacity: 1, overflow: "hidden"}
      ]);
      input.value = "";
      focusTarget = input;
    } else {
      const target = document.getElementById(deleting ? nextId : row.id);
      focusTarget = target?.querySelector(".toggle") || input;
      if (!deleting) {
        motion(target?.querySelector(".indicator"), [{opacity: .25, transform: "scale(.85)"}, {opacity: 1, transform: "none"}]);
        motion(target?.querySelector(".task-title"), [{opacity: .4}, {opacity: 1}]);
      }
    }
    input.removeAttribute("aria-invalid");
    feedback.textContent = adding ? "Задача добавлена." : deleting ? "Задача удалена." : "Статус обновлён.";
  } catch (failure) {
    feedback.textContent = "";
    actionError.textContent = failure instanceof TypeError
      ? "Связь с сервером прервалась. Обновите страницу, чтобы проверить результат."
      : failure.message;
  } finally {
    saving = false;
    button.removeAttribute("aria-busy");
    buttons.forEach(item => { item.disabled = false; });
    input.readOnly = false;
    if (document.activeElement === document.body || form.contains(document.activeElement)) {
      focusTarget.focus({preventScroll: true});
    }
  }
});
