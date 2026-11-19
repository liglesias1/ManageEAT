/* Menu performance: every dish classified as star, plowhorse, puzzle or dog within its category. */
"use strict";

const menuPage = startPage({
  title: "Menu performance",
  intro: "Which dishes sell, which ones make money, and what to do with each. Every dish is compared only with " +
         "the other dishes of its category.",
});

// Writes each dish's name next to its dot, and the quadrant names in the corners
const quadrantLabels = {
  id: "labels",
  afterDatasetsDraw(chart) {
    const { ctx, chartArea: area } = chart;
    ctx.save();
    ctx.font = "600 11px sans-serif";
    ctx.fillStyle = "#b3bcb8";
    ctx.textAlign = "right";
    ctx.fillText("STARS", area.right - 8, area.top + 16);
    ctx.fillText("PLOWHORSES", area.right - 8, area.bottom - 8);
    ctx.textAlign = "left";
    ctx.fillText("PUZZLES", area.left + 8, area.top + 16);
    ctx.fillText("DOGS", area.left + 8, area.bottom - 8);
    ctx.font = "12px sans-serif";
    ctx.fillStyle = "#1f2623";
    chart.getDatasetMeta(0).data.forEach((point, i) => {
      const name = chart.data.datasets[0].data[i].name;
      const nearRightEdge = point.x > area.right - 130;
      ctx.textAlign = nearRightEdge ? "right" : "left";
      ctx.fillText(name, point.x + (nearRightEdge ? -11 : 11), point.y + 4);
    });
    ctx.restore();
  },
};

// Rounds an axis limit up to a "nice" number (e.g. 1,880 -> 2,000) so the ticks read well
function niceCeil(value) {
  const step = 10 ** Math.floor(Math.log10(value)) / 2;
  return Math.ceil(value / step) * step;
}

function drawMenuChart(canvas, dishes) {
  const style = getComputedStyle(document.documentElement);
  const colour = (cls) => style.getPropertyValue("--" + cls).trim();
  const xs = dishes.map((d) => d.units_sold);
  const ys = dishes.map((d) => d.margin);
  const threshold = dishes[0].popularity_threshold;
  const average = dishes[0].average_margin;
  const xMax = niceCeil(Math.max(...xs, threshold) * 1.1);
  const yMin = Math.floor(Math.min(...ys, average) - 1);
  const yMax = Math.ceil(Math.max(...ys, average) + 1);
  const dashed = { type: "line", borderColor: "#b3bcb8", borderDash: [5, 5], borderWidth: 1, pointRadius: 0 };
  new Chart(canvas, {
    type: "scatter",
    plugins: [quadrantLabels],
    data: {
      datasets: [
        { data: dishes.map((d) => ({ x: d.units_sold, y: d.margin, name: d.name })),
          backgroundColor: dishes.map((d) => colour(d.class)), pointRadius: 7, pointHoverRadius: 9 },
        { ...dashed, data: [{ x: threshold, y: yMin }, { x: threshold, y: yMax }] },
        { ...dashed, data: [{ x: 0, y: average }, { x: xMax, y: average }] },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { filter: (item) => item.datasetIndex === 0,
                   callbacks: { label: (c) => `${c.raw.name}: ${c.raw.x} sold, ${eur(c.raw.y)} margin` } },
      },
      scales: {
        x: { min: 0, max: xMax, title: { display: true, text: "Units sold" } },
        y: { min: yMin, max: yMax, title: { display: true, text: "Margin per dish (€)" } },
      },
    },
  });
}

mount(menuPage, async () => {
  const data = await api("sales", "/sales/menu");
  const s = data.summary;
  const categories = Object.keys(data.by_category).filter((c) => data.by_category[c].length);
  return {
    html: html`
      ${kpis([
        { icon: "money", label: "Revenue", value: eur(s.revenue), note: "All dishes and drinks sold" },
        { icon: "trend", label: "Gross margin", value: eur(s.gross_margin), note: "Revenue minus ingredient cost" },
        { icon: "pie", label: "Food cost", value: pct(s.food_cost_pct), note: "Share of revenue spent on ingredients" },
        { icon: "star", label: "Best-selling dish", small: true, value: s.best_seller || "–",
          note: s.least_ordered ? `Least ordered: ${s.least_ordered}` : "" },
      ])}
      <section class="card">
        <h2>Popularity vs. margin</h2>
        <p class="hint">Each dot is a dish. Dashed lines mark the popularity threshold and the average margin of the category.
          <span class="badge star">Star</span> sells well, high margin · <span class="badge plowhorse">Plowhorse</span> sells well, low margin ·
          <span class="badge puzzle">Puzzle</span> high margin, rarely ordered · <span class="badge dog">Dog</span> low sales, low margin</p>
        ${categories.length ? html`
          <div class="tabs">${categories.map((c) => html`<button class="tab" data-key="${c}">${capitalize(c)}s</button>`)}</div>
          ${categories.map((c) => html`
            <div class="tab-panel" data-panel="${c}">
              <div class="chart-box"><canvas id="chart-${c}"></canvas></div>
              <table>
                <thead><tr><th>Dish</th><th class="num">Sold</th><th class="num">Price</th><th class="num">Cost</th>
                           <th class="num">Margin</th><th>Class</th></tr></thead>
                <tbody>${data.by_category[c].map((d) => html`
                  <tr><td>${d.name}<span class="dish-note">${d.recommendation}</span></td>
                      <td class="num">${d.units_sold}</td><td class="num">${eur(d.avg_price)}</td>
                      <td class="num">${eur(d.unit_cost)}</td><td class="num">${eur(d.margin)}</td>
                      <td><span class="badge ${d.class}">${capitalize(d.class)}</span></td></tr>`)}
                </tbody>
              </table>
            </div>`)}` : html`<p class="muted">No dish has been sold yet.</p>`}
        ${data.new_dishes.length ? html`
          <h3 class="subhead">New on the menu</h3>
          <p class="hint">Not sold yet, so they are not classified. <a class="link" href="dishes.html">See their recipes →</a></p>
          <p>${data.new_dishes.map((d) => html`<span class="badge new">${d.name}</span> `)}</p>` : ""}
      </section>`,
    after: (root) => setUpTabs(root, (category) =>
      drawMenuChart(document.getElementById("chart-" + category), data.by_category[category])),
  };
});