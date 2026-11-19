/* Inventory: stock of every ingredient, what to reorder, the suppliers, and the forms to add both. */
"use strict";

const inventoryPage = startPage({ title: "Inventory" });

function statusBadge(status) {
  if (status === "out") return html`<span class="badge dog">Out</span>`;
  if (status === "reorder") return html`<span class="badge plowhorse">Reorder</span>`;
  return html`<span class="badge star">OK</span>`;
}

function ingredientForm(suppliers, asOf) {
  return html`
    <form class="form ingredient-form" id="ingredient-form">
      <div class="ingredient-fields">
        <label>Name<input name="name" required minlength="2" maxlength="60" placeholder="Mascarpone"></label>
        <label>Unit<select name="unit">${["kg", "l", "unit"].map((u) => html`<option value="${u}">${u}</option>`)}</select></label>
        <label>Price per unit (€)<input name="unit_cost" type="number" step="0.01" min="0.01" required></label>
        <label>Stock now<input name="counted_stock" type="number" step="any" min="0" required></label>
        <label>Reorder below<input name="reorder_level" type="number" step="any" min="0" required></label>
        <label>Counted on<input name="counted_at" type="date" value="${asOf || ""}" required></label>
      </div>
      <fieldset class="choices supplier-choice">
        <legend>Who sells it?</legend>
        <div class="segmented">
          <label class="choice"><input type="radio" name="supplier_choice" value="existing" checked> A supplier we already have</label>
          <label class="choice"><input type="radio" name="supplier_choice" value="new"> A new supplier</label>
        </div>
        <div class="supplier-panel" data-choice="existing">
          <label>Supplier<select name="supplier_id"><option value="">Choose…</option>
            ${suppliers.map((s) => html`<option value="${s.id}">${s.name} · delivers in ${s.lead_time_days} d</option>`)}</select></label>
        </div>
        <div class="supplier-panel new-supplier-fields" data-choice="new" hidden>
          <label>Supplier name<input name="new_supplier_name" placeholder="Quesos Italia"></label>
          <label>Phone<input name="new_supplier_phone" placeholder="+34 600 000 000"></label>
          <label>Email<input name="new_supplier_email" type="email" placeholder="orders@supplier.com"></label>
          <label>Delivery time (days)<input name="new_supplier_lead_time" type="number" min="0" max="60"></label>
        </div>
      </fieldset>
      <button type="submit">Add ingredient</button>
    </form>`;
}

function supplierForm(ingredients) {
  return html`
    <form class="form" id="supplier-form">
      <label>Name<input name="name" required minlength="2" maxlength="80"></label>
      <label>Phone<input name="phone" placeholder="+34 600 000 000"></label>
      <label>Email<input name="email" type="email" placeholder="orders@supplier.com"></label>
      <label>Delivery time (days)<input name="lead_time_days" type="number" min="0" max="60" required></label>
      <fieldset class="choices">
        <legend>What does it supply? <span class="muted">Ticked ingredients move to this supplier</span></legend>
        ${ingredients.map((i) => html`
          <label class="choice"><input type="checkbox" name="ingredient_ids" value="${i.id}"> ${i.name} <span class="muted">· ${i.supplier}</span></label>`)}
      </fieldset>
      <button type="submit">Add supplier</button>
    </form>`;
}

mount(inventoryPage, async () => {
  const data = await api("sales", "/sales/inventory");
  const s = data.summary;
  setHeading("Inventory", html`Stock left of every ingredient, worked out from the last stocktake and what the recipes used since then,
    and what to order before it runs out. Figures as of ${data.as_of || "–"}.`);
  return {
    html: html`
      ${kpis([
        { icon: "warning", label: "To reorder", value: s.to_reorder, note: "Low, or will run out before a delivery arrives" },
        { icon: "out", label: "Out of stock", value: s.out_of_stock, note: "Ingredients already used up" },
        { icon: "inventory", label: "Stock value", value: eur(s.stock_value), note: "What is in the store room at cost price" },
        { icon: "cart", label: "Suggested orders", value: eur(s.order_value), note: "Cost of everything below" },
      ])}
      <section class="card">
        <h2>Stock levels</h2>
        <p class="hint">Most urgent first. A suggested order covers the supplier's delivery time plus one week.
          <span class="badge dog">Out</span> · <span class="badge plowhorse">Reorder</span> · <span class="badge star">OK</span></p>
        ${data.stock.length ? html`<table>
          <thead><tr><th>Ingredient</th><th>Supplier</th><th class="num">In stock</th><th class="num">Used per day</th>
                     <th class="num">Days left</th><th class="num">Delivery</th><th>Status</th><th class="num">Order</th></tr></thead>
          <tbody>${data.stock.map((i) => html`
            <tr><td>${i.name} <a class="link small" href="ingredient.html?id=${i.id}">Edit</a></td>
                <td><a class="link" href="supplier.html?id=${i.supplier_id}">${i.supplier}</a></td>
                <td class="num">${num(Math.max(i.current, 0), 1)} ${i.unit}</td>
                <td class="num">${num(i.daily_use, 1)}</td>
                <td class="num">${i.days_left === null ? "–" : num(i.days_left, 1)}</td>
                <td class="num">${i.lead_time_days} d</td>
                <td>${statusBadge(i.status)}</td>
                <td class="num">${i.suggested_order ? html`<strong>${i.suggested_order} ${i.unit}</strong>` : "–"}</td></tr>`)}
          </tbody>
        </table>` : html`<p class="muted">No ingredients yet. Add the first one below.</p>`}
      </section>
      <section class="card" id="new-ingredient">
        <h2>Add an ingredient</h2>
        <p class="hint">A new product the kitchen buys, how much there is now and who sells it. It can then be used in recipes.</p>
        ${ingredientForm(data.suppliers, data.as_of)}
      </section>
      <div class="split">
        <section class="card" id="new-supplier">
          <h2>Add a supplier</h2>
          <p class="hint">Every supplier needs a phone number or an email so orders can be placed.</p>
          ${supplierForm(data.ingredients)}
        </section>
        <section class="card">
          <h2>Suppliers</h2>
          <p class="hint">Who to call when something runs low. Click a supplier to see prices and spending.</p>
          ${data.suppliers.length ? html`<table>
            <thead><tr><th>Supplier</th><th>Contact</th><th class="num">Delivery</th><th>Supplies</th></tr></thead>
            <tbody>${data.suppliers.map((sup) => html`
              <tr><td><a class="link" href="supplier.html?id=${sup.id}">${sup.name}</a></td>
                  <td class="muted">${sup.phone ? html`<div class="nowrap">${sup.phone}</div>` : ""}${sup.email ? html`<div>${sup.email}</div>` : ""}</td>
                  <td class="num">${sup.lead_time_days} d</td><td class="muted">${sup.supplies || "Nothing yet"}</td></tr>`)}
            </tbody>
          </table>` : html`<p class="muted">No suppliers yet.</p>`}
        </section>
      </div>`,
    after: (root) => {
      const ingredient = root.querySelector("#ingredient-form");
      const showChoice = () => {
        const choice = ingredient.querySelector("input[name=supplier_choice]:checked").value;
        ingredient.querySelectorAll(".supplier-panel").forEach((panel) => { panel.hidden = panel.dataset.choice !== choice; });
      };
      ingredient.querySelectorAll("input[name=supplier_choice]").forEach((r) => r.addEventListener("change", showChoice));
      handleForm(ingredient, {
        build: (f) => {
          const isNew = f.supplier_choice.value === "new";
          return {
            name: f.name.value.trim(), unit: f.unit.value, unit_cost: Number(f.unit_cost.value),
            counted_stock: Number(f.counted_stock.value), reorder_level: Number(f.reorder_level.value),
            counted_at: f.counted_at.value,
            supplier_id: isNew ? null : numberOrNull(f.supplier_id.value),
            new_supplier: isNew ? { name: textOrNull(f.new_supplier_name.value), phone: textOrNull(f.new_supplier_phone.value),
                                    email: textOrNull(f.new_supplier_email.value),
                                    lead_time_days: numberOrNull(f.new_supplier_lead_time.value) } : null,
          };
        },
        send: (body) => api("sales", "/sales/ingredients", { method: "POST", body }),
        done: (answer) => {
          flash(`Ingredient “${answer.name}” added. Record its first delivery below, or use it in a dish.`);
          location.href = `supplier.html?id=${answer.supplier_id}`;
        },
      });
      handleForm(root.querySelector("#supplier-form"), {
        build: (f) => ({
          name: f.name.value.trim(), phone: textOrNull(f.phone.value), email: textOrNull(f.email.value),
          lead_time_days: Number(f.lead_time_days.value),
          ingredient_ids: Array.from(f.querySelectorAll("input[name=ingredient_ids]:checked")).map((c) => Number(c.value)),
        }),
        send: (body) => api("sales", "/sales/suppliers", { method: "POST", body }),
        done: (answer) => {
          flash(`Supplier “${answer.name}” added.`);
          location.href = `supplier.html?id=${answer.id}`;
        },
      });
    },
  };
});