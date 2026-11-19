/* Edit ingredient: its price, supplier and reorder level, or a new stock count. */
"use strict";

const ingredientPage = startPage({ title: "Edit ingredient" });
const ingredientId = Number(queryParam("id"));

mount(ingredientPage, async () => {
  const [item, inventory] = await Promise.all([
    api("sales", `/sales/ingredients/${ingredientId}`),
    api("sales", "/sales/inventory"),
  ]);
  setHeading(`Edit ${item.name}`, html`Change its price, its supplier or the reorder level, or record a new stock count.
    <a class="link" href="inventory.html">← Back to inventory</a>`);
  return {
    html: html`
      <section class="card">
        <form class="form" id="ingredient-form">
          <div class="ingredient-fields">
            <label>Name<input name="name" required minlength="2" maxlength="60" value="${item.name}"></label>
            <label>Unit<select name="unit">${["kg", "l", "unit"].map((u) => html`
              <option value="${u}" ${item.unit === u ? raw("selected") : ""}>${u}</option>`)}</select></label>
            <label>Price per unit (€)<input name="unit_cost" type="number" step="0.01" min="0.01" value="${item.unit_cost}" required></label>
            <label>Stock counted<input name="counted_stock" type="number" step="any" min="0" value="${item.counted_stock}" required></label>
            <label>Counted on<input name="counted_at" type="date" value="${item.counted_at}" required></label>
            <label>Reorder below<input name="reorder_level" type="number" step="any" min="0" value="${item.reorder_level}" required></label>
          </div>
          <label>Supplier<select name="supplier_id" required>${inventory.suppliers.map((s) => html`
            <option value="${s.id}" ${s.id === item.supplier_id ? raw("selected") : ""}>${s.name} · delivers in ${s.lead_time_days} d</option>`)}
          </select></label>
          <p class="muted">A new stock count replaces the old one: current stock is worked out again from this count, the deliveries
            received and what the recipes used since that day. A new price changes the cost of every dish that uses it.
            New supplier? <a class="link" href="inventory.html#new-supplier">Add it first →</a></p>
          <button type="submit">Save changes</button>
        </form>
      </section>`,
    after: (root) => handleForm(root.querySelector("#ingredient-form"), {
      build: (f) => ({
        name: f.name.value.trim(), unit: f.unit.value, unit_cost: Number(f.unit_cost.value),
        counted_stock: Number(f.counted_stock.value), counted_at: f.counted_at.value,
        reorder_level: Number(f.reorder_level.value), supplier_id: Number(f.supplier_id.value), new_supplier: null,
      }),
      send: (body) => api("sales", `/sales/ingredients/${ingredientId}`, { method: "PUT", body }),
      done: () => { flash(`Ingredient “${item.name}” updated.`); location.href = "inventory.html"; },
    }),
  };
});