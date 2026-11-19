/* Menu & recipes: every dish with its price, ingredient cost and margin, and the form to add one. */
"use strict";

const dishesPage = startPage({
  title: "Menu & recipes",
  intro: "Every dish on the menu with its price, what its ingredients cost and how much is left for the restaurant. " +
         "Costs are calculated from each recipe and the current price of its ingredients.",
});

function foodCostMeter(dish, target) {
  const width = Math.min(dish.food_cost_pct, 100);
  return html`
    <div class="meter ${dish.above_target ? "over" : ""}" title="${pct(dish.food_cost_pct)}">
      <span style="width: ${width}%"></span><i style="left: ${target}%"></i>
    </div>
    <span class="meter-label ${dish.above_target ? "over" : ""}">${pct(dish.food_cost_pct)}${dish.above_target ? " · review price" : ""}</span>`;
}

mount(dishesPage, async () => {
  const data = await api("sales", "/sales/dishes");
  const s = data.summary;
  const categories = data.categories.filter((c) => data.by_category[c].length);
  return {
    html: html`
      ${kpis([
        { icon: "menu", label: "Dishes on the menu", value: s.dishes, note: "Food and drinks" },
        { icon: "pie", label: "Average food cost", value: pct(s.avg_food_cost_pct), note: "Share of the price spent on ingredients" },
        { icon: "warning", label: `Above ${data.target}% food cost`, value: s.above_target, note: "Dishes whose price may be too low" },
        { icon: "trend", label: "Highest food cost", small: true, value: s.highest ? s.highest.name : "–",
          note: s.highest ? `${pct(s.highest.food_cost_pct)} of its price` : "" },
      ])}
      <section class="card">
        <h2>The menu</h2>
        <p class="hint"><strong>Markup</strong>: how much the price is above the ingredient cost.
          <strong>Food cost</strong>: share of the price spent on ingredients (restaurants aim for ${data.target}% or less).
          Click a dish to see its recipe and edit it.</p>
        ${categories.length ? html`
          <div class="tabs">${categories.map((c) => html`<button class="tab" data-key="${c}">${capitalize(c)}s</button>`)}</div>
          ${categories.map((c) => html`
            <div class="dish-panel" data-panel="${c}">
              <table class="dishes">
                <thead><tr><th>Dish</th><th class="num">Price</th><th class="num">Ingredients</th><th class="num">Margin</th>
                           <th class="num">Markup</th><th>Food cost</th></tr></thead>
                <tbody>${data.by_category[c].map((d) => html`
                  <tr>
                    <td><details><summary>${d.name} <span class="muted">${d.code}</span></summary>
                      <a class="link small" href="dish.html?code=${encodeURIComponent(d.code)}">Edit dish and recipe →</a>
                      <table class="recipe">${d.recipe.map((line) => html`
                        <tr><td>${line.ingredient}</td><td class="num">${line.quantity} ${line.unit}</td>
                            <td class="num muted">× ${eur(line.unit_cost)}</td><td class="num">${eur(line.line_cost)}</td></tr>`)}
                      </table></details></td>
                    <td class="num">${eur(d.price)}</td><td class="num">${eur(d.cost)}</td><td class="num">${eur(d.margin)}</td>
                    <td class="num">${d.markup_pct === null ? "–" : `+${num(d.markup_pct)}%`}</td>
                    <td>${foodCostMeter(d, data.target)}</td>
                  </tr>`)}
                </tbody>
              </table>
            </div>`)}` : html`<p class="muted">The menu is empty. Add the first dish below.</p>`}
      </section>
      <section class="card" id="new-dish">
        <h2>Add a dish</h2>
        <p class="hint">Choose its type, set the price and build its recipe. The cost is worked out from the ingredients.
          Missing an ingredient? <a class="link" href="inventory.html#new-ingredient">Add it in Inventory →</a></p>
        ${data.ingredients.length ? dishForm({ categories: data.categories, ingredients: data.ingredients, target: data.target, button: "Add dish" })
          : html`<p class="muted">Add an ingredient in Inventory first.</p>`}
      </section>`,
    after: (root) => {
      setUpTabs(root);
      const form = root.querySelector(".dish-form");
      if (form) {
        setUpDishForm(form, (body) => api("sales", "/sales/dishes", { method: "POST", body }), (answer) => {
          flash(`Dish “${answer.name}” added to the menu as ${answer.code}.`);
          location.reload();
        });
      }
    },
  };
});