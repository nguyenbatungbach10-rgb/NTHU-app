// JavaScript chỉ lo phần giao diện: gọi Calendar API và mở hộp thoại.
// Mọi kiểm tra dữ liệu và quy tắc nghiệp vụ nằm ở phía Python (calendar_logic.py).

const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

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
    throw new Error((data && data.error) || `Request failed (${response.status})`);
  }
  return data;
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
      button.textContent = "Saved ✓";
    } catch (error) {
      button.disabled = false;
      button.textContent = "Try again";
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
    heading.textContent = editingId ? "Edit event" : "Add event";
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
    if (!confirm("Delete this event?")) return;
    try {
      await api("DELETE", `/api/events/${editingId}`);
      location.reload();
    } catch (error) {
      errorBox.textContent = error.message;
    }
  });
}
