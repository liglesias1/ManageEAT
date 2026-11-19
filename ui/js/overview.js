/* Overview: the month's key figures and what needs attention, assembled in the browser from both
 * services (ADR-6). Each service is asked on its own, so if one is down the other's part still shows. */
"use strict";

const overview = startPage({ title: "Overview", intro: "How the restaurant is doing and what needs your attention." });

function serviceDown(result) {
  return notice(result.reason instanceof ServiceUnavailable ? "warning" : "error", result.reason.message);
}

function attentionItems(sales, personnel) {
  const items = [];
  if (sales) {
    if (sales.to_reorder.length) {
      items.push({ text: `${sales.to_reorder.length} ingredients to reorder: ${sales.to_reorder.slice(0, 5).join(", ")}` +
                         (sales.to_reorder.length > 5 ? "…" : ""), page: "Inventory", link: "inventory.html" });
    }
    if (sales.dogs.length) {
      items.push({ text: `Low sales and low margin: ${sales.dogs.join(", ")}`, page: "Menu performance", link: "menu.html" });
    }
    if (sales.pl.net_profit !== null && sales.pl.net_profit < 0) {
      items.push({ text: `The restaurant is losing money in ${sales.month}`, page: "Profit & loss", link: "profit-loss.html" });
    }
  }
  if (personnel && personnel.schedule && personnel.schedule.short) {
    items.push({ text: `${personnel.schedule.short} hour and role combinations are short of staff` +
                       (personnel.schedule.most_missing_role ? `, most of all ${personnel.schedule.most_missing_role}` : ""),
                 page: "Schedule", link: "schedule.html" });
  }
  return items;
}

mount(overview, async () => {
  const [salesResult, personnelResult] = await Promise.allSettled([
    api("sales", "/sales/summary"),
    api("personnel", "/personnel/summary"),
  ]);
  if (salesResult.status === "rejected" && personnelResult.status === "rejected") throw salesResult.reason;
  const sales = salesResult.status === "fulfilled" ? salesResult.value : null;
  const personnel = personnelResult.status === "fulfilled" ? personnelResult.value : null;

  if (sales) {
    setHeading("Overview", html`How the restaurant is doing in ${sales.month || "the period"} and what needs your attention.
      Sales data from ${sales.start || "–"} to ${sales.end || "–"}.`);
  }
  const pl = sales ? sales.pl : null;
  const attention = attentionItems(sales, personnel);

  return {
    html: html`
      ${sales ? html`
        ${sourceNotice(sales.wages, WAGES_NOTICES)}
        ${kpis([
          { icon: "trend", label: "Net profit", value: eur(pl.net_profit),
            note: pl.net_margin_pct === null ? "Needs the wages from personnel" : `${pct(pl.net_margin_pct)} of revenue` },
          { icon: "money", label: "Revenue", value: eur(pl.revenue), note: "Everything charged to customers" },
          { icon: "menu", label: "Food cost", value: pct(pl.ingredients_pct), note: "Ingredients as a share of revenue" },
          { icon: "staff", label: "Labour cost", value: pct(pl.labor_pct), note: "Wages as a share of revenue" },
        ])}` : serviceDown(salesResult)}

      <section class="card attention">
        <h2>Needs your attention</h2>
        ${attention.length ? html`<ul>${attention.map((item) => html`
          <li>${icon("warning")}<span>${item.text}</span><a class="link" href="${item.link}">${item.page} →</a></li>`)}</ul>`
          : html`<p class="muted">Nothing urgent. Everything is within its limits.</p>`}
      </section>

      <div class="overview-grid">
        ${sales ? html`
          <a class="card section" href="menu.html">
            <p class="nav-group">Sales</p><h2>Menu performance</h2>
            <dl><dt>Best-selling dish</dt><dd>${sales.menu.best_seller || "–"}</dd>
                <dt>Stars</dt><dd>${sales.menu.class_counts.star}</dd>
                <dt>Dogs</dt><dd>${sales.menu.class_counts.dog}</dd></dl>
            <span class="link">Open →</span>
          </a>
          <a class="card section" href="inventory.html">
            <p class="nav-group">Sales</p><h2>Inventory</h2>
            <dl><dt>To reorder</dt><dd>${sales.inventory.to_reorder + sales.inventory.out_of_stock}</dd>
                <dt>Stock value</dt><dd>${eur(sales.inventory.stock_value)}</dd>
                <dt>Suggested order</dt><dd>${eur(sales.inventory.order_value)}</dd></dl>
            <span class="link">Open →</span>
          </a>
          <a class="card section" href="profit-loss.html">
            <p class="nav-group">Sales</p><h2>Profit &amp; loss</h2>
            <dl><dt>Gross profit</dt><dd>${eur(pl.gross_profit)}</dd>
                <dt>Fixed expenses</dt><dd>${eur(pl.fixed)}</dd>
                <dt>Net margin</dt><dd>${pct(pl.net_margin_pct)}</dd></dl>
            <span class="link">Open →</span>
          </a>` : ""}
        ${personnel ? html`
          <a class="card section" href="schedule.html">
            <p class="nav-group">Personnel</p><h2>Schedule</h2>
            <dl><dt>Busiest hour</dt>
                <dd>${personnel.schedule && personnel.schedule.peak ? `${personnel.schedule.peak.day_name} ${personnel.schedule.peak.hour}:00` : "–"}</dd>
                <dt>Understaffed slots</dt><dd>${personnel.schedule ? personnel.schedule.short : "–"}</dd>
                <dt>Most needed role</dt><dd>${personnel.schedule ? personnel.schedule.most_missing_role || "None" : "–"}</dd></dl>
            <span class="link">Open →</span>
          </a>
          <a class="card section" href="payroll.html">
            <p class="nav-group">Personnel</p><h2>Payroll</h2>
            <dl><dt>Wages</dt><dd>${eur(personnel.wages)}</dd>
                <dt>Employees</dt><dd>${personnel.employees}</dd>
                <dt>Hours worked</dt><dd>${num(personnel.hours)}</dd></dl>
            <span class="link">Open →</span>
          </a>` : html`<div class="card section"><p class="nav-group">Personnel</p>${serviceDown(personnelResult)}</div>`}
      </div>
      ${personnel ? sourceNotice(personnel.demand, DEMAND_NOTICES) : ""}`,
  };
});