/* Profit & loss: the flow that crosses the seam on the server. Sales calculates the statement and asks
 * personnel for the wages; this page shows whether those wages are live, a snapshot or unavailable. */
"use strict";

const plPage = startPage({ title: "Profit & loss" });
const requestedMonth = queryParam("month");

function statementRows(pl) {
  const share = (value) => (value === null ? "–" : pct(value));
  return html`
    <tr><td>Revenue</td><td class="num">${eur(pl.revenue)}</td><td class="num">100.0%</td></tr>
    <tr><td class="indent">− Ingredients used</td><td class="num">${eur(pl.ingredients)}</td><td class="num">${share(pl.ingredients_pct)}</td></tr>
    <tr class="subtotal"><td>Gross profit</td><td class="num">${eur(pl.gross_profit)}</td>
        <td class="num">${pl.revenue ? pct(100 - pl.ingredients_pct) : "0.0%"}</td></tr>
    <tr><td class="indent">− Wages <span class="muted">(from payroll)</span></td><td class="num">${eur(pl.labor)}</td><td class="num">${share(pl.labor_pct)}</td></tr>
    <tr><td class="indent">− Fixed expenses</td><td class="num">${eur(pl.fixed)}</td><td class="num">${share(pl.fixed_pct)}</td></tr>
    <tr class="total"><td>Net profit</td><td class="num">${eur(pl.net_profit)}</td><td class="num">${share(pl.net_margin_pct)}</td></tr>`;
}

function drawWeeks(canvas, weeks) {
  const label = (w) => `${w.start.slice(8)}–${w.end.slice(8)} ${new Date(w.start).toLocaleString("en", { month: "short" })}`;
  new Chart(canvas, {
    data: {
      labels: weeks.map(label),
      datasets: [
        { type: "bar", label: "Ingredients", data: weeks.map((w) => w.ingredients), backgroundColor: "#c9a26b", stack: "costs" },
        { type: "bar", label: "Wages", data: weeks.map((w) => w.labor), backgroundColor: "#7d8f6a", stack: "costs" },
        { type: "bar", label: "Fixed", data: weeks.map((w) => w.fixed), backgroundColor: "#b9b1a3", stack: "costs" },
        { type: "bar", label: "Profit", data: weeks.map((w) => w.profit), backgroundColor: "#7d2633", stack: "costs" },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" },
                 tooltip: { callbacks: { label: (c) => `${c.dataset.label}: €${Math.round(c.raw).toLocaleString()}` } } },
      scales: { x: { stacked: true }, y: { stacked: true, ticks: { callback: (v) => "€" + v.toLocaleString() } } },
    },
  });
}

function drawHistory(canvas, history) {
  const months = history.slice().reverse();          // oldest first, left to right
  new Chart(canvas, {
    type: "bar",
    data: {
      labels: months.map((h) => h.month),
      datasets: [{ label: "Net profit", data: months.map((h) => h.net_profit),
                   backgroundColor: months.map((h) => (h.net_profit < 0 ? "#a3392e" : "#7d2633")) }],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false },
                 tooltip: { callbacks: { label: (c) => `Net profit: €${Math.round(c.raw).toLocaleString()}` } } },
      scales: { y: { ticks: { callback: (v) => "€" + v.toLocaleString() } } },
    },
  });
}

mount(plPage, async () => {
  const data = await api("sales", "/sales/profit-loss" + (requestedMonth ? `?month=${encodeURIComponent(requestedMonth)}` : ""));
  const pl = data.pl;
  setHeading("Profit & loss", html`What the restaurant earned in ${data.month} once ingredients, wages and fixed costs are paid,
    with a week-by-week breakdown and the history of every month recorded.
    ${data.start ? `Sales data from ${data.start} to ${data.end}${data.in_progress ? " (month in progress)" : ""}.` : ""}`);

  return {
    html: html`
      <nav class="month-nav">
        <a class="month-step" href="profit-loss.html?month=${data.prev_month}">← ${data.prev_month}</a>
        <span class="month-picker"><label>Month <input type="month" id="month-input" value="${data.month}"></label></span>
        ${data.next_month ? html`<a class="month-step" href="profit-loss.html?month=${data.next_month}">${data.next_month} →</a>` : ""}
        ${data.in_progress ? html`<span class="badge new">Month in progress</span>` : ""}
      </nav>
      ${sourceNotice(data.wages, WAGES_NOTICES)}
      ${data.has_data ? html`
        ${kpis([
          { icon: "trend", label: "Net profit", value: eur(pl.net_profit),
            note: pl.net_margin_pct === null ? "Needs the wages from personnel" : `${pct(pl.net_margin_pct)} of revenue` },
          { icon: "money", label: "Revenue", value: eur(pl.revenue), note: "Everything charged to customers" },
          { icon: "menu", label: "Food cost", value: pct(pl.ingredients_pct), note: "Ingredients as a share of revenue" },
          { icon: "staff", label: "Labour cost", value: pct(pl.labor_pct), note: "Wages as a share of revenue" },
        ])}
        <div class="split">
          <section class="card">
            <h2>Statement for ${data.month}</h2>
            <p class="hint">Where each euro of revenue goes.</p>
            <table class="statement"><thead><tr><th></th><th class="num">Amount</th><th class="num">% of revenue</th></tr></thead>
              <tbody>${statementRows(pl)}</tbody></table>
          </section>
          <section class="card">
            <h2>Week by week</h2>
            <p class="hint">Revenue against each cost. Fixed expenses are shared out by number of days.</p>
            ${pl.weeks.length ? html`<div class="chart-box"><canvas id="weeks-chart"></canvas></div>`
              : html`<p class="muted">No sales recorded in this month yet, so there is no weekly breakdown.</p>`}
          </section>
        </div>` : html`
        <section class="card empty-month">
          <h2>No data recorded for ${data.month}</h2>
          <p class="hint">There are no sales and no fixed expenses for this month. Use the arrows to move to another month, or add a fixed expense below.</p>
        </section>`}
      <div class="split">
        <section class="card" id="new-expense">
          <h2>Add a fixed expense</h2>
          <p class="hint">Monthly costs that do not depend on sales: rent, utilities, insurance…</p>
          <form class="form" id="expense-form">
            <label>Description<input name="description" required minlength="2" maxlength="80" placeholder="Rent"></label>
            <label>Amount (€)<input name="amount" type="number" step="0.01" min="0.01" required></label>
            <label>Month<input name="month" type="month" value="${data.month}" required></label>
            <button type="submit">Add expense</button>
          </form>
        </section>
        <section class="card">
          <h2>Fixed expenses in ${data.month}</h2>
          <p class="hint">Included in the statement above.</p>
          ${data.expenses.length ? html`<table>
            <thead><tr><th>Expense</th><th class="num">Amount</th></tr></thead>
            <tbody>${data.expenses.map((e) => html`<tr><td>${e.description}</td><td class="num">${eur(e.amount)}</td></tr>`)}
              <tr class="total"><td>Total</td><td class="num">${eur(pl.fixed)}</td></tr></tbody>
          </table>` : html`<p class="muted">No fixed expenses recorded for this month.</p>`}
        </section>
      </div>
      ${data.history.length ? html`
        <section class="card">
          <h2>Month by month</h2>
          <p class="hint">Every month with recorded data, newest first. Choose a month to see its full statement.</p>
          <div class="chart-box small"><canvas id="history-chart"></canvas></div>
          <table>
            <thead><tr><th>Month</th><th class="num">Revenue</th><th class="num">Ingredients</th><th class="num">Wages</th>
                       <th class="num">Fixed</th><th class="num">Net profit</th><th class="num">Margin</th></tr></thead>
            <tbody>${data.history.map((h) => html`
              <tr class="${h.month === data.month ? "selected" : ""}">
                <td><a class="link" href="profit-loss.html?month=${h.month}">${h.month}</a></td>
                <td class="num">${eur(h.revenue)}</td><td class="num">${eur(h.ingredients)}</td><td class="num">${eur(h.labor)}</td>
                <td class="num">${eur(h.fixed)}</td><td class="num">${eur(h.net_profit)}</td><td class="num">${pct(h.net_margin_pct)}</td>
              </tr>`)}
            </tbody>
          </table>
        </section>` : ""}`,
    after: () => {
      document.getElementById("month-input").addEventListener("change", (event) => {
        if (event.target.value) location.href = `profit-loss.html?month=${event.target.value}`;
      });
      const weeksCanvas = document.getElementById("weeks-chart");
      if (weeksCanvas) drawWeeks(weeksCanvas, pl.weeks);
      const historyCanvas = document.getElementById("history-chart");
      if (historyCanvas) drawHistory(historyCanvas, data.history);
      handleForm(document.getElementById("expense-form"), {
        build: (f) => ({ description: f.description.value.trim(), amount: Number(f.amount.value), month: f.month.value }),
        send: (body) => api("sales", "/sales/expenses", { method: "POST", body }),
        done: (answer) => {
          flash(`Expense “${answer.description}” added to ${answer.month}.`);
          // Opens the month the expense belongs to; if it is already on screen, reloads it
          if (location.search === `?month=${answer.month}`) location.reload();
          else location.href = `profit-loss.html?month=${answer.month}`;
        },
      });
    },
  };
});