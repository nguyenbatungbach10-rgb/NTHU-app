// JavaScript chỉ lo phần giao diện: gọi Calendar API và mở hộp thoại.
// Mọi kiểm tra dữ liệu và quy tắc nghiệp vụ nằm ở phía Python (calendar_logic.py).

const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

// Dịch chữ hiển thị: bản dịch do Python gửi xuống (window.I18N trong base.html); tiếng Anh thì giữ nguyên.
const t = (text) => (window.I18N && window.I18N[text]) || text;

// Gọi API: tự gắn CSRF token, gửi/nhận JSON, ném lỗi kèm thông báo của server.
async function api(method, url, body) {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    credentials: "same-origin",
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error((data && data.error) || `${t("Request failed")} (${response.status})`);
  }
  return data;
}

// ---------- Thông báo nhỏ (toast) nổi lên vài giây ----------
let toastTimer;
function showToast(title, sub) {
  const box = document.getElementById("toast");
  if (!box) return;
  box.querySelector(".toast-title").textContent = title;
  box.querySelector(".toast-sub").textContent = sub || "";
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.hidden = true; }, 3500);
}

// ---------- Nút "Save to Calendar" trên trang Announcements ----------
document.querySelectorAll("[data-save]").forEach((button) => {
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      await api("POST", "/api/events", {
        title: button.dataset.title,
        date: button.dataset.date,
        description: button.dataset.office,
        source_url: button.dataset.url,
      });
      button.textContent = `✓ ${t("Added")}`;
      button.classList.add("is-added");
      const kind = button.dataset.kind === "deadline" ? "Deadline added to your calendar" : "Added to your calendar";
      showToast(t(kind), `${button.dataset.title} · ${button.dataset.date}`);
    } catch (error) {
      button.disabled = false;
      button.textContent = t("Try again");
      button.title = error.message;
    }
  });
});

// ---------- Trang Calendar: hộp thoại thêm / sửa / xóa sự kiện ----------
const dialog = document.getElementById("event-dialog");

if (dialog) {
  const form = dialog.querySelector("form");
  const heading = dialog.querySelector("h2");
  const deleteButton = dialog.querySelector("[data-delete]");
  const errorBox = dialog.querySelector(".form-error");
  const sourceLine = dialog.querySelector(".source-line");
  const sourceLink = document.getElementById("ev-source");
  let editingId = null; // null = đang thêm mới

  function openDialog(event) {
    editingId = event.id || null;
    heading.textContent = t(editingId ? "Edit event" : "Add event");
    form.elements.title.value = event.title || "";
    form.elements.date.value = event.date || "";
    form.elements.time.value = event.time || "";
    form.elements.description.value = event.description || "";
    deleteButton.hidden = !editingId;
    errorBox.textContent = "";
    sourceLine.hidden = !event.url;
    if (event.url) sourceLink.href = event.url;
    dialog.showModal();
  }

  document.querySelectorAll("[data-add]").forEach((button) => {
    button.addEventListener("click", () => openDialog({ date: button.dataset.date }));
  });

  document.querySelectorAll("[data-event]").forEach((pill) => {
    pill.addEventListener("click", () => openDialog(pill.dataset));
  });

  dialog.querySelector("[data-cancel]").addEventListener("click", () => dialog.close());

  form.addEventListener("submit", async (submitEvent) => {
    submitEvent.preventDefault();
    const payload = {
      title: form.elements.title.value,
      date: form.elements.date.value,
      time: form.elements.time.value,
      description: form.elements.description.value,
    };
    try {
      if (editingId) {
        await api("PUT", `/api/events/${editingId}`, payload);
      } else {
        await api("POST", "/api/events", payload);
      }
      location.reload(); // vẽ lại lịch từ dữ liệu mới
    } catch (error) {
      errorBox.textContent = error.message;
    }
  });

  deleteButton.addEventListener("click", async () => {
    if (!confirm(t("Delete this event?"))) return;
    try {
      await api("DELETE", `/api/events/${editingId}`);
      location.reload();
    } catch (error) {
      errorBox.textContent = error.message;
    }
  });
}

// ---------- Trang GPA: hộp thoại môn học và form mục tiêu ----------
const courseDialog = document.getElementById("course-dialog");

if (courseDialog) {
  const form = courseDialog.querySelector("form");
  const heading = courseDialog.querySelector("h2");
  const deleteButton = courseDialog.querySelector("[data-delete]");
  const errorBox = courseDialog.querySelector(".form-error");
  let editingId = null; // null = đang thêm mới

  function openCourseDialog(course) {
    editingId = course.id || null;
    heading.textContent = t(editingId ? "Edit course" : "Add course");
    form.elements.name.value = course.name || "";
    form.elements.credits.value = course.credits || "3";
    form.elements.semester.value = course.semester || "";
    form.elements.grade.value = course.grade || "";
    deleteButton.hidden = !editingId;
    errorBox.textContent = "";
    courseDialog.showModal();
  }

  document.querySelectorAll("[data-add-course]").forEach((button) => {
    button.addEventListener("click", () => openCourseDialog({ semester: button.dataset.semester }));
  });
  document.querySelectorAll("[data-course]").forEach((button) => {
    button.addEventListener("click", () => openCourseDialog(button.dataset));
  });
  courseDialog.querySelector("[data-cancel]").addEventListener("click", () => courseDialog.close());

  form.addEventListener("submit", async (submitEvent) => {
    submitEvent.preventDefault();
    const payload = {
      name: form.elements.name.value,
      credits: form.elements.credits.value === "" ? null : Number(form.elements.credits.value),
      semester: form.elements.semester.value,
      grade: form.elements.grade.value,
    };
    try {
      if (editingId) {
        await api("PUT", `/api/courses/${editingId}`, payload);
      } else {
        await api("POST", "/api/courses", payload);
      }
      location.reload(); // Python tính lại toàn bộ số liệu
    } catch (error) {
      errorBox.textContent = error.message;
    }
  });

  deleteButton.addEventListener("click", async () => {
    if (!confirm(t("Delete this course?"))) return;
    try {
      await api("DELETE", `/api/courses/${editingId}`);
      location.reload();
    } catch (error) {
      errorBox.textContent = error.message;
    }
  });
}

const goalForm = document.getElementById("goal-form");

// Thanh kéo mục tiêu GPA <-> ô số: chỉ hiển thị cho khớp nhau, Python kiểm tra khi bấm Save
(() => {
  const range = document.getElementById("goal-range");
  const number = document.getElementById("goal-gpa");
  const shown = document.getElementById("goal-value");
  if (!range || !number) return;
  range.addEventListener("input", () => { number.value = Number(range.value).toFixed(2); shown.value = number.value; });
  number.addEventListener("input", () => { range.value = number.value; if (number.value) shown.value = Number(number.value).toFixed(2); });
})();

if (goalForm) {
  goalForm.addEventListener("submit", async (submitEvent) => {
    submitEvent.preventDefault();
    const errorBox = document.getElementById("goal-error");
    try {
      await api("PUT", "/api/goals", {
        target_gpa: goalForm.elements.target_gpa.value === "" ? null : Number(goalForm.elements.target_gpa.value),
        credits_required: goalForm.elements.credits_required.value === "" ? null : Number(goalForm.elements.credits_required.value),
      });
      location.reload();
    } catch (error) {
      errorBox.textContent = error.message;
    }
  });
}

// ---------- Trang Study: ba hộp thoại (việc, môn học, buổi học) ----------

// Tạo một hộp thoại thêm/sửa/xóa. Trả về hàm open(dữ liệu) để mở hộp thoại.
//   endpoint: ví dụ "/api/tasks"; noun: chữ hiện trên tiêu đề
//   fill(form, data): đổ dữ liệu vào form; toPayload(form): đọc form thành JSON gửi lên
function crudDialog(dialogId, endpoint, noun, fill, toPayload) {
  const dlg = document.getElementById(dialogId);
  if (!dlg) return () => {};
  const form = dlg.querySelector("form");
  const heading = dlg.querySelector("h2");
  const deleteButton = dlg.querySelector("[data-delete]");
  const errorBox = dlg.querySelector(".form-error");
  let editingId = null; // null = đang thêm mới

  dlg.querySelector("[data-cancel]").addEventListener("click", () => dlg.close());

  form.addEventListener("submit", async (submitEvent) => {
    submitEvent.preventDefault();
    try {
      if (editingId) await api("PUT", `${endpoint}/${editingId}`, toPayload(form));
      else await api("POST", endpoint, toPayload(form));
      location.reload(); // Python tính lại mọi thứ từ dữ liệu mới
    } catch (error) {
      errorBox.textContent = error.message;
    }
  });

  deleteButton.addEventListener("click", async () => {
    if (!confirm(t(`Delete this ${noun}?`))) return;
    try {
      await api("DELETE", `${endpoint}/${editingId}`);
      location.reload();
    } catch (error) {
      errorBox.textContent = error.message;
    }
  });

  return function open(data) {
    editingId = data.id || null;
    heading.textContent = t(data.heading || `${editingId ? "Edit" : "Add"} ${noun}`);
    fill(form, data);
    deleteButton.hidden = !editingId;
    errorBox.textContent = "";
    dlg.showModal();
  };
}

// "" -> null, "5" -> 5 (API cần số nguyên hoặc null cho các trường id)
const idOrNull = (value) => (value === "" || value === undefined ? null : Number(value));

const openTask = crudDialog(
  "task-dialog", "/api/tasks", "task",
  (form, data) => {
    form.elements.title.value = data.title || "";
    form.elements.due_date.value = data.due || "";
    form.elements.subject_id.value = data.subject || "";
    form.elements.parent_id.value = data.parent || "";
    form.elements.done.value = data.done === "1" ? "1" : "";
    // Việc con dùng môn của việc cha nên ẩn ô chọn môn
    form.querySelector("[data-subject-field]").hidden = !!data.parent;
  },
  (form) => ({
    title: form.elements.title.value,
    due_date: form.elements.due_date.value,
    subject_id: idOrNull(form.elements.subject_id.value),
    parent_id: idOrNull(form.elements.parent_id.value),
    done: form.elements.done.value === "1",
  }),
);

const openSubject = crudDialog(
  "subject-dialog", "/api/subjects", "subject",
  (form, data) => {
    form.elements.name.value = data.name || "";
    form.elements.notes.value = data.notes || "";
  },
  (form) => ({ name: form.elements.name.value, notes: form.elements.notes.value }),
);

const openSession = crudDialog(
  "session-dialog", "/api/sessions", "session",
  (form, data) => {
    form.elements.date.value = data.date || "";
    form.elements.minutes.value = data.minutes || "";
    form.elements.subject_id.value = data.subject || "";
    form.elements.note.value = data.note || "";
  },
  (form) => ({
    date: form.elements.date.value,
    minutes: form.elements.minutes.value === "" ? null : Number(form.elements.minutes.value),
    subject_id: idOrNull(form.elements.subject_id.value),
    note: form.elements.note.value,
  }),
);

document.querySelectorAll("[data-add-task]").forEach((button) => {
  button.addEventListener("click", () => openTask(
    button.dataset.parent ? { parent: button.dataset.parent, heading: "Add step" } : {}));
});
document.querySelectorAll("[data-task]").forEach((button) => {
  button.addEventListener("click", () => openTask(button.dataset));
});
document.querySelectorAll("[data-add-subject]").forEach((button) => {
  button.addEventListener("click", () => openSubject({}));
});
document.querySelectorAll("[data-subject-edit]").forEach((button) => {
  button.addEventListener("click", () => openSubject(button.dataset));
});
document.querySelectorAll("[data-add-session]").forEach((button) => {
  button.addEventListener("click", () => openSession({ date: button.dataset.date }));
});
document.querySelectorAll("[data-session]").forEach((button) => {
  button.addEventListener("click", () => openSession(button.dataset));
});

// Ô tick "xong": gửi lại toàn bộ việc với done đã đổi
document.querySelectorAll("[data-toggle]").forEach((box) => {
  box.addEventListener("change", async () => {
    const edit = box.closest("li").querySelector("[data-task]").dataset;
    try {
      await api("PUT", `/api/tasks/${box.dataset.id}`, {
        title: edit.title,
        due_date: edit.due,
        subject_id: idOrNull(edit.subject),
        done: box.checked,
      });
      location.reload();
    } catch (error) {
      box.checked = !box.checked;
      alert(error.message);
    }
  });
});

// ---------- Trang Schedule: hộp thoại thêm / sửa / xóa môn học ----------
const openClass = crudDialog(
  "class-dialog", "/api/classes", "class",
  (form, data) => {
    form.elements.name.value = data.name || "";
    form.elements.weekday.value = data.weekday === undefined ? "0" : data.weekday;
    form.elements.start.value = data.start || "";
    form.elements.end.value = data.end || "";
    form.elements.room.value = data.room || "";
  },
  (form) => ({
    name: form.elements.name.value,
    weekday: Number(form.elements.weekday.value),
    start: form.elements.start.value,
    end: form.elements.end.value,
    room: form.elements.room.value,
  }),
);

document.querySelectorAll("[data-add-class]").forEach((button) => {
  button.addEventListener("click", () =>
    openClass({ weekday: button.dataset.weekday, start: button.dataset.start, end: button.dataset.end }));
});
document.querySelectorAll("[data-class]").forEach((card) => {
  card.addEventListener("click", () => openClass(card.dataset));
});

// ---------- Menu 3 gạch (thả xuống) ----------
// Chỉ đóng/mở giao diện: bấm nút, bấm ra ngoài, hoặc nhấn Esc để đóng.
// Hai nút mở cùng một menu: nút ☰ ở thanh trên (máy tính) và tab "More" dưới đáy (điện thoại).
(() => {
  const buttons = [...document.querySelectorAll("[data-menu-toggle]")];
  const panel = document.getElementById("site-menu");
  if (!buttons.length || !panel) return;
  let opener = buttons[0];

  function setOpen(open) {
    buttons.forEach((b) => b.setAttribute("aria-expanded", String(open)));
    const top = document.getElementById("menu-button");
    if (top) top.setAttribute("aria-label", open ? top.dataset.labelClose : top.dataset.labelOpen);
    panel.hidden = !open;
    panel.classList.toggle("as-sheet", open && opener !== top);   // mở từ tab dưới đáy -> bảng trượt từ dưới
  }

  buttons.forEach((b) => b.addEventListener("click", () => { opener = b; setOpen(panel.hidden); }));
  document.addEventListener("click", (event) => {
    if (!panel.hidden && !panel.contains(event.target) && !buttons.some((b) => b.contains(event.target))) setOpen(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) {
      setOpen(false);
      opener.focus();
    }
  });
})();

// ---------- Calendar: bảng chọn nhanh tháng/năm đóng khi bấm ra ngoài hoặc nhấn Esc ----------
(() => {
  const jump = document.querySelector("details.jump");
  if (!jump) return;
  document.addEventListener("click", (event) => {
    if (jump.open && !jump.contains(event.target)) jump.open = false;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && jump.open) {
      jump.open = false;
      jump.querySelector("summary").focus();
    }
  });
})();

// ---------- Nút sáng/tối ở thanh trên ----------
// Khi đang "theo hệ thống", chế độ thật phụ thuộc máy; JS chỉ chọn giá trị ngược lại trước khi gửi form.
document.querySelector("[data-theme-toggle]")?.addEventListener("click", (event) => {
  const mode = document.documentElement.dataset.theme;
  const dark = mode === "dark" || (mode === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
  event.currentTarget.value = dark ? "light" : "dark";
});


// Nút "Copy": chép chữ trong ô (link lịch) vào bộ nhớ tạm
document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const field = document.querySelector(button.dataset.copy);
    try {
      await navigator.clipboard.writeText(field.value);
    } catch {
      field.select();
      document.execCommand("copy");
    }
    showToast(t("Copied"), field.value);
  });
});

// Đăng ký service worker (static/sw.js) để web cài được như app và có trang offline.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});   // lỗi thì web vẫn chạy bình thường
  });
}
