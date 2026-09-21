/** Shared pieces for the two performance modules (same design). */
import { GENDER_LABELS, classLabel } from "../../shared/constants.js";
import { Modal, Toast, badge, emptyState } from "../../shared/components.js";
import { escapeHtml, formatDate } from "../../shared/utils.js";

export function shortDate(iso) {
  const p = String(iso || "").split("-");
  return p.length === 3 ? `${Number(p[2])}/${Number(p[1])}` : String(iso || "");
}

/** Number dropdown options (from..to) with the current value pre-selected. */
export function nOptions(selected, from = 1, to = 12) {
  let out = "";
  for (let i = from; i <= to; i++) {
    out += `<option value="${i}"${Number(selected) === i ? " selected" : ""}>${i}</option>`;
  }
  return out;
}

export function trendChart(points) {
  const W = 640, H = 250, P = { top: 26, right: 14, bottom: 30, left: 36 };
  const iw = W - P.left - P.right, ih = H - P.top - P.bottom;
  const base = P.top + ih;
  const max = Math.max(1, ...points.map((p) => p.present));
  const slot = iw / points.length;
  const barW = Math.min(52, slot * 0.52);
  const y = (v) => base - (v / (max * 1.2 || 1)) * ih;
  const grid = [0, 1, 2, 3, 4].map((g) => {
    const v = Math.round((max * 1.2 * g) / 4);
    const yy = y(v);
    return `<line x1="${P.left}" y1="${yy}" x2="${W - P.right}" y2="${yy}" class="chart-grid" />
      <text x="${P.left - 6}" y="${yy + 4}" class="chart-ylabel">${v}</text>`;
  }).join("");
  const bars = points.map((p, i) => {
    const cx = P.left + slot * i + slot / 2;
    const top = y(p.present);
    const h = Math.max(2, base - top);
    const isMax = p.present === max && max > 0;
    return `
    <rect x="${(cx - barW / 2).toFixed(1)}" y="${top.toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}"
      rx="7" class="chart-bar${isMax ? " max" : ""}">
      <title>${escapeHtml(formatDate(p.date))}: حاضر ${p.present} / غائب ${p.absent}</title>
    </rect>
    <text x="${cx.toFixed(1)}" y="${(top - 7).toFixed(1)}" class="chart-val">${p.present}</text>
    <text x="${cx.toFixed(1)}" y="${H - 8}" class="chart-xlabel">${escapeHtml(shortDate(p.date))}</text>`;
  }).join("");
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="منحنى الحضور">
    ${grid}<line x1="${P.left}" y1="${base}" x2="${W - P.right}" y2="${base}" class="chart-base" />${bars}</svg>`;
}

export function groupList(groups, { singleClass, emptyTitle, emptyMsg, rowBadge, onBoy }) {
  const classes = Object.keys(groups).filter((c) => groups[c].length);
  if (!classes.length) {
    return emptyState(emptyTitle, emptyMsg);
  }
  const showHead = classes.length > 1 || !singleClass;
  const html = classes.map((c) => `
    <div class="class-group">
      ${showHead ? `<h3>${escapeHtml(classLabel(c))}</h3>` : ""}
      <ul class="name-list">
        ${groups[c].map((b) => `
          <li><strong>${escapeHtml(b.boy_name)}</strong>
            <span style="display:flex;gap:6px;align-items:center">${rowBadge(b)}
            <button class="btn btn-secondary btn-sm" data-boy="${b.boy_id}">عرض الملف</button></span></li>`).join("")}
      </ul>
    </div>`).join("");
  return { html, bind: (root) => {
    root.querySelectorAll("[data-boy]").forEach((btn) => {
      btn.addEventListener("click", () => onBoy(btn.dataset.boy));
    });
  } };
}

export async function openBoyModal(service, boyId) {
  try {
    const p = await service.boyProfile(boyId);
    const b = p.boy;
    const row = (k, v) => `<div class="detail-row"><span>${k}</span><span>${v || "—"}</span></div>`;
    const hist = p.history.length
      ? `<div class="table-wrap"><table class="table hist-table"><thead>
           <tr><th>التاريخ</th><th>الحالة</th><th>ملاحظة</th></tr></thead><tbody>
           ${p.history.map((h) => `<tr>
             <td>${escapeHtml(h.action_date || "—")}</td>
             <td>${h.attend === "y" ? badge("حاضر", "green") : badge("غائب", "red")}</td>
             <td>${h.note ? escapeHtml(h.note) : "—"}</td></tr>`).join("")}
         </tbody></table></div>`
      : `<p class="muted">لا يوجد سجل حضور لهذا الولد بعد.</p>`;
    const notes = p.notes.length
      ? `<ul class="notes-list">${p.notes.map((n) => `<li>${escapeHtml(n)}</li>`).join("")}</ul>`
      : `<p class="muted">لا توجد ملاحظات.</p>`;
    Modal.open({
      title: b.boy_name || "ملف الولد",
      sub: `${classLabel(b.class_name)} • نسبة الحضور ${p.percent}% (${p.present}/${p.total})`,
      body: `<div class="details" style="margin-bottom:12px">
          ${row("النوع", GENDER_LABELS[b.gender] || "—")}
          ${row("تاريخ الميلاد", b.birth_date || "—")}
          ${row("السن", b.age ?? "—")}
          ${row("التليفون", b.phone || "—")}
          ${row("العنوان", b.address || "—")}
        </div>
        <h3 style="margin:8px 0">سجل الحضور الكامل</h3>${hist}
        <h3 style="margin:12px 0 4px">الملاحظات</h3>${notes}`,
      actions: [{ label: "إغلاق", kind: "btn-primary" }],
    });
  } catch (err) {
    Toast.error(err.message);
  }
}
