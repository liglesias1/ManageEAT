/* Schedule: recommended against actual staff for every opening hour. The diners per hour come from
 * the sales service, so this page shows whether they are live, a snapshot or unavailable (ADR-6). */
"use strict";

const schedulePage = startPage({
  title: "Schedule",
  intro: "When the restaurant is busiest and how many people each role needs at every hour, compared with the " +
         "staff that actually clocked in. Averages for each weekday over the whole period.",
});

function heatColour(level) {
  return `background: rgba(125, 38, 51, ${(0.08 + level * 0.85).toFixed(2)}); color: ${level > 0.5 ? "#fff" : "inherit"}`;
}

mount(schedulePage, async () => {
  const data = await api("personnel", "/personnel/schedule");
  const top = sourceNotice(data.demand, DEMAND_NOTICES);
  if (!data.summary) {
    return { html: html`${top}<section class="card"><h2>Roles</h2>
      <p class="hint">The schedule needs the diners per hour from sales. These are the roles it will use:</p>
      <p>${data.roles.join(", ") || "No roles yet."} <a class="link" href="staff.html">Manage staff →</a></p></section>` };
  }
  const covers = {};
  data.heatmap.forEach((cell) => { covers[`${cell.weekday}-${cell.hour}`] = cell.covers; });
  const days = data.weekdays.filter((day) => data.by_day[day].length);
  const s = data.summary;

  return {
    html: html`
      ${top}
      ${kpis([
        { icon: "clock", label: "Busiest hour", small: true, value: s.peak ? `${s.peak.day_name} ${s.peak.hour}:00` : "–",
          note: s.peak ? `${num(s.peak.covers)} diners on average` : "" },
        { icon: "warning", label: "Understaffed", value: s.short, note: "Hour and role combinations short of people" },
        { icon: "staff", label: "Overstaffed", value: s.extra, note: "Hour and role combinations with at least one person spare" },
        { icon: "person", label: "Most needed role", small: true, value: s.most_missing_role || "None",
          note: "Role with the largest shortfall overall" },
      ])}
      <section class="card">
        <h2>Demand by day and hour</h2>
        <p class="hint">Average number of diners. The darker the cell, the busier the restaurant.</p>
        <table class="heatmap">
          <thead><tr><th></th>${data.hours.map((h) => html`<th class="num">${h}:00</th>`)}</tr></thead>
          <tbody>${data.weekdays.map((day, weekday) => html`
            <tr><th>${day}</th>${data.hours.map((hour) => {
              const value = covers[`${weekday}-${hour}`] || 0;
              const level = data.max_covers ? value / data.max_covers : 0;
              return html`<td class="num" style="${heatColour(level)}">${num(value)}</td>`;
            })}</tr>`)}
          </tbody>
        </table>
      </section>
      <section class="card">
        <h2>Recommended vs. actual staff</h2>
        <p class="hint">Each cell shows <strong>needed / on shift</strong> for that role and hour.
          <span class="badge dog">Short</span> people are missing · <span class="badge plowhorse">Extra</span> at least one person spare</p>
        <div class="tabs">${days.map((day) => html`<button class="tab" data-key="${day}">${day}</button>`)}</div>
        ${days.map((day) => html`
          <div class="day-panel" data-panel="${day}">
            <table>
              <thead><tr><th>Hour</th><th class="num">Diners</th>${data.roles.map((r) => html`<th class="num">${r}</th>`)}</tr></thead>
              <tbody>${data.by_day[day].map((slot) => html`
                <tr><td>${slot.hour}:00</td><td class="num">${num(slot.covers)}</td>
                  ${slot.roles.map((cell) => html`<td class="num staff-${cell.status}">${cell.needed} / ${Number(cell.actual.toFixed(1))}</td>`)}
                </tr>`)}
              </tbody>
            </table>
          </div>`)}
      </section>`,
    after: (root) => setUpTabs(root),
  };
});