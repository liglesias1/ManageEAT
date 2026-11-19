/* The dish form, shared by "Add a dish" (dishes.html) and "Edit dish" (dish.html): name, type, price and
 * the recipe, with a live preview of the cost. The service calculates the cost again when it saves. */
"use strict";

function dishForm({ categories, ingredients, target, dish, button }) {
  const recipe = dish ? dish.recipe : [];
  const rows = Math.max(8, recipe.length + 2);
  const options = (selected) => html`<option value="">–</option>${ingredients.map((i) => html`
    <option value="${i.id}" data-cost="${i.unit_cost}" data-unit="${i.unit}" ${String(selected) === String(i.id) ? raw("selected") : ""}>
      ${i.name} (${eur(i.unit_cost)}/${i.unit})</option>`)}`;
  return html`
    <form class="form dish-form" data-target="${target}">
      <div class="dish-fields">
        <label>Name<input name="name" required minlength="2" maxlength="60" placeholder="Tiramisu" value="${dish ? dish.name : ""}"></label>
        <label>Type<select name="category" required><option value="">Choose…</option>
          ${categories.map((c) => html`<option value="${c}" ${dish && dish.category === c ? raw("selected") : ""}>${capitalize(c)}</option>`)}
        </select></label>
        <label>Price (€)<input name="price" type="number" step="0.01" min="0.01" max="500" required value="${dish ? dish.price : ""}"></label>
      </div>
      <fieldset class="choices recipe-rows">
        <legend>Recipe: ingredients for one portion <span class="muted">(leave a row empty to remove it)</span></legend>
        ${Array.from({ length: rows }, (_, n) => html`
          <div class="recipe-row">
            <select name="ingredient_id">${options(recipe[n] ? recipe[n].ingredient_id : "")}</select>
            <input name="quantity" type="number" step="any" min="0" placeholder="Quantity" value="${recipe[n] ? recipe[n].quantity : ""}">
            <span class="unit muted"></span>
          </div>`)}
      </fieldset>
      <div class="preview">
        <div><span class="muted">Ingredient cost</span><strong class="preview-cost">€0.00</strong></div>
        <div><span class="muted">Margin</span><strong class="preview-margin">–</strong></div>
        <div><span class="muted">Markup</span><strong class="preview-markup">–</strong></div>
        <div><span class="muted">Food cost</span><strong class="preview-fc">–</strong></div>
      </div>
      <button type="submit">${button}</button>
    </form>`;
}

/* Live preview of the cost, and the body the API expects: {name, category, price, recipe: [...]}. */
function setUpDishForm(form, send, done) {
  const target = Number(form.dataset.target);
  const preview = () => {
    let cost = 0;
    form.querySelectorAll(".recipe-row").forEach((row) => {
      const option = row.querySelector("select").selectedOptions[0];
      const quantity = parseFloat(row.querySelector("input").value) || 0;
      row.querySelector(".unit").textContent = option.dataset.unit || "";
      cost += (parseFloat(option.dataset.cost) || 0) * quantity;
    });
    const price = parseFloat(form.price.value) || 0;
    form.querySelector(".preview-cost").textContent = eur(cost);
    form.querySelector(".preview-margin").textContent = price ? eur(price - cost) : "–";
    form.querySelector(".preview-markup").textContent = price && cost ? `+${Math.round((price - cost) / cost * 100)}%` : "–";
    const foodCost = form.querySelector(".preview-fc");
    foodCost.textContent = price ? pct(cost / price * 100) : "–";
    foodCost.classList.toggle("over", price > 0 && (cost / price) * 100 > target);
  };
  form.addEventListener("input", preview);
  preview();

  handleForm(form, {
    build: (f) => ({
      name: f.name.value.trim(),
      category: f.category.value,
      price: Number(f.price.value),
      recipe: Array.from(f.querySelectorAll(".recipe-row"))
        .map((row) => ({ ingredient_id: Number(row.querySelector("select").value), quantity: Number(row.querySelector("input").value) }))
        .filter((line) => line.ingredient_id && line.quantity),
    }),
    send,
    done,
  });
}