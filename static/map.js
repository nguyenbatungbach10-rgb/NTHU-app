// Trang Campus map. JavaScript chỉ vẽ bản đồ và hiển thị.
// Dữ liệu, phân loại, tìm kiếm và khoảng cách đều do Python làm (map_logic.py qua /api/places...).
(() => {
  const box = document.getElementById("map");
  if (!box) return;
  const results = document.getElementById("map-results");
  const resultsTitle = document.getElementById("results-title");
  const detailBox = document.getElementById("place-detail");
  const input = document.getElementById("map-q");
  const placeUrl = (id) => box.dataset.placeUrl.replace("__id__", encodeURIComponent(id));
  const t = (text) => (window.I18N && window.I18N[text]) || text;   // bản dịch do Python gửi xuống
  let map = null;
  let ready = false;   // true khi bản đồ và các lớp địa điểm đã tải xong
  let popup = null;
  let mode = "2d";
  const savedHeights = {}; // chiều cao gốc của các lớp nhà 3D, để bật/tắt 3D

  // Tạo phần tử có class và chữ (textContent nên tên lấy từ dữ liệu không thể chèn HTML lạ)
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // ---------- danh sách kết quả tìm kiếm (giống macro result_item trong map.html) ----------
  function resultItem(p) {
    const button = el("button", "map-result");
    button.type = "button";
    button.dataset.place = p.id;
    button.style.setProperty("--dot", p.color);
    const text = el("span");
    text.append(el("strong", "", p.name));
    if (p.name_en) text.append(el("small", "", p.name_en));
    button.append(el("span", "dot"), text);
    const li = el("li");
    li.append(button);
    return li;
  }

  async function runSearch(q) {
    const response = await fetch(`${box.dataset.searchUrl}?q=${encodeURIComponent(q)}`);
    const list = response.ok ? await response.json() : [];
    results.replaceChildren(...list.map(resultItem));
    if (!list.length) {
      results.append(el("li", "muted", q.trim() ? t('No place matches "{q}".').replace("{q}", q) : t("Type a name to search.")));
    }
    resultsTitle.textContent = t(q.trim() ? "Results" : "Places");
    return list;
  }

  let timer = null;
  input?.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => runSearch(input.value), 200);
  });
  input?.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const list = await runSearch(input.value);
    if (list.length) focusPlace(list[0].id);
  });
  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-place]");
    if (target) focusPlace(target.dataset.place);
  });

  // ---------- khung chi tiết một địa điểm ----------
  function detailNode(d) {
    const root = el("div", "map-pop");
    root.append(el("strong", "", d.name));
    if (d.name_en) root.append(el("div", "en", d.name_en));
    root.append(el("div", "cat", d.category_label + (d.floors_text ? `, ${d.floors_text}` : "")));
    const near = Object.values(d.nearby);
    if (near.length) {
      const list = el("ul");
      near.forEach((n) => list.append(el("li", "", n.text)));   // câu đã được Python dịch và điền số
      root.append(list);
    }
    const link = el("a", "", d.directions_label);
    link.href = d.directions_url;
    link.target = "_blank";
    link.rel = "noopener";
    root.append(link);
    return root;
  }

  async function focusPlace(id) {
    const response = await fetch(placeUrl(id));
    if (!response.ok) return;
    const d = await response.json();
    if (!ready) { // bản đồ không tải được: hiện chi tiết ngay trong cột bên trái
      detailBox.replaceChildren(detailNode(d));
      detailBox.hidden = false;
      return;
    }
    map.flyTo({ center: [d.lon, d.lat], zoom: Math.max(map.getZoom(), 17), essential: true });
    popup?.remove();
    popup = new maplibregl.Popup({ offset: 12, maxWidth: "290px" })
      .setLngLat([d.lon, d.lat]).setDOMContent(detailNode(d)).addTo(map);
  }

  // ---------- lọc theo nhóm (nhóm hiện sẵn do Python chọn qua aria-pressed) ----------
  function applyFilter() {
    if (!ready) return;
    const on = [...document.querySelectorAll("[data-category][aria-pressed='true']")].map((b) => b.dataset.category);
    const filter = ["in", ["get", "category"], ["literal", on]];
    map.setFilter("places-dot", filter);
    map.setFilter("places-label", filter);
  }
  document.querySelectorAll("[data-category]").forEach((button) => button.addEventListener("click", () => {
    button.setAttribute("aria-pressed", String(button.getAttribute("aria-pressed") !== "true"));
    applyFilter();
  }));

  // ---------- 2D / 3D ----------
  // Lớp nhà 3D (fill-extrusion) của kiểu bản đồ; nếu kiểu bản đồ không có thì tự thêm một lớp.
  function extrusionLayers() {
    const layers = map.getStyle().layers;
    const ids = layers.filter((l) => l.type === "fill-extrusion").map((l) => l.id);
    if (ids.length) return ids;
    const base = layers.find((l) => l["source-layer"] === "building");
    if (!base) return [];
    map.addLayer({
      id: "nthu-3d", type: "fill-extrusion", source: base.source, "source-layer": "building", minzoom: 14,
      paint: {
        "fill-extrusion-color": "#d9d0ea",
        "fill-extrusion-height": ["coalesce", ["get", "render_height"], 8],
        "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
        "fill-extrusion-opacity": 0.9,
      },
    }, "places-dot");
    return ["nthu-3d"];
  }

  function setMode(next) {
    mode = next;
    document.querySelectorAll("[data-mode]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
    if (!ready) return; // bản đồ chưa sẵn sàng: áp dụng khi tải xong
    const is3d = mode === "3d";
    for (const id of extrusionLayers()) {
      if (!(id in savedHeights)) {
        savedHeights[id] = map.getPaintProperty(id, "fill-extrusion-height") ?? ["coalesce", ["get", "render_height"], 8];
      }
      map.setPaintProperty(id, "fill-extrusion-height", is3d ? savedHeights[id] : 0); // 2D: nhà phẳng
    }
    map.easeTo({ pitch: is3d ? 60 : 0, bearing: is3d ? -20 : 0, zoom: is3d ? Math.max(map.getZoom(), 16.3) : map.getZoom(), duration: 900 });
    if (is3d) { map.dragRotate.enable(); map.touchZoomRotate.enableRotation(); }
    else { map.dragRotate.disable(); map.touchZoomRotate.disableRotation(); }
  }
  document.querySelectorAll("[data-mode]").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));

  // ---------- tạo bản đồ ----------
  function showFallback() {
    document.getElementById("map-fallback").hidden = false;
  }

  if (!window.maplibregl || !box.dataset.center) { showFallback(); return; }
  try {
    map = new maplibregl.Map({
      container: box,
      style: box.dataset.style,
      center: box.dataset.center.split(",").map(Number),
      zoom: 15.6,
      maxBounds: [[120.94, 24.765], [121.03, 24.815]], // chỉ quanh hai cơ sở ở Tân Trúc
      attributionControl: { compact: true },
    });
  } catch (error) {
    showFallback();
    return;
  }
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  map.addControl(new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: true }, trackUserLocation: true }), "top-right");
  map.addControl(new maplibregl.ScaleControl(), "bottom-left");
  map.on("error", () => { if (!ready && !map.isStyleLoaded()) showFallback(); });

  map.on("load", async () => {
    const data = await (await fetch(box.dataset.placesUrl)).json();
    // Dùng lại font chữ mà kiểu bản đồ đang dùng (chữ Hán được trình duyệt tự vẽ)
    const styleFont = map.getStyle().layers.map((l) => l.layout?.["text-font"]).find((f) => Array.isArray(f) && typeof f[0] === "string");
    map.addSource("places", { type: "geojson", data });
    map.addLayer({
      id: "places-dot", type: "circle", source: "places",
      paint: {
        "circle-color": ["get", "color"],
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 14, 3.5, 18, 8],
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 1.5,
      },
    });
    map.addLayer({
      id: "places-label", type: "symbol", source: "places", minzoom: 16.3,
      layout: {
        "text-field": ["get", "name"], "text-font": styleFont || ["Noto Sans Regular"], "text-size": 12,
        "text-offset": [0, 1.1], "text-anchor": "top", "text-optional": true,
      },
      paint: { "text-color": "#1f1433", "text-halo-color": "#ffffff", "text-halo-width": 1.4 },
    });
    ready = true;
    document.getElementById("map-fallback").hidden = true;
    applyFilter();
    setMode(mode);
    map.on("click", "places-dot", (event) => focusPlace(event.features[0].properties.id));
    map.on("mouseenter", "places-dot", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "places-dot", () => { map.getCanvas().style.cursor = ""; });
    if (box.dataset.focus) focusPlace(box.dataset.focus);
  });

  document.querySelectorAll("[data-campus]").forEach((button) => button.addEventListener("click", () => {
    map?.flyTo({ center: [Number(button.dataset.lon), Number(button.dataset.lat)], zoom: 16, essential: true });
  }));
})();
