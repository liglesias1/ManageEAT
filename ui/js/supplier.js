/* One supplier: its products and prices, its deliveries, and the forms to record a delivery and to edit it. */
"use strict";

const supplierPage = startPage({ title: "Supplier" });
const supplierId = Number(queryParam("id"));

mount(supplierPage, async () => {
  const data = await api("sales", `/sales/suppliers/${supplierId}`);
  const sup = data.supplier;
  const s = data.summary;
  const contact = [sup.phone, sup.email].filter(Boolean).join(" · ");
  setHeading(sup.name, html`${contact}${contact ? " · " : ""}Delivers in ${sup.lead_time_days} days.
    <a class="link" href="inventory.html">← Back to inventory</a>`);
  return {
    html: html`
      ${kpis([
        { icon: "cart", label: "Purchased", value: eur(s.purchased), note: `${s.deliveries} deliveries recorded` },
        { icon: "money", label: "Used at cost", value: eur(s.spend), note: "What the recipes used in the period" },
        { icon: "warning", label: "To reorder", value: s.to_reorder, note: `Suggested order: ${eur(s.order_value)}` },
        { icon: "truck", label: "Delivery time", value: `${sup.lead_time_days} days`, note: "From order to arrival" },
      ])}
      <section class="card">
        <h2>Products and prices</h2>
        <p class="hint">Current price per unit, how much was used during the period and what is left.</p>
        ${data.items.length ? html`<table>
          <thead><tr><th>Product</th><th class="num">Price</th><th class="num">Used in period</th><th class="num">Used at cost</th>
                     <th class="num">In stock</th><th>Status</th><th class="num">Order</th></tr></thead>
          <tbody>${data.items.map((i) => html`
            <tr><td>${i.name} <a class="link small" href="ingredient.html?id=${i.id}">Edit</a></td>
                <td class="num">${eur(i.unit_cost)} / ${i.unit}</td>
                <td class="num">${num(i.used_in_period || 0, 1)} ${i.unit}</td>
                <td class="num">${eur(i.spend_in_period)}</td>
                <td class="num">${num(Math.max(i.current, 0), 1)} ${i.unit}</td>
                <td>${i.status === "out" ? html`<span class="badge dog">Out</span>` : i.status === "reorder"
                      ? html`<span class="badge plowhorse">Reorder</span>` : html`<span class="badge star">OK</span>`}</td>
                <td class="num">${i.suggested_order ? `${i.suggested_order} ${i.unit}` : "–"}</td></tr>`)}
          </tbody>
        </table>` : html`<p class="muted">This supplier does not supply any ingredient yet.</p>`}
      </section>
      <div class="split">
        <section class="card" id="new-delivery">
          <h2>Record a delivery</h2>
          <p class="hint">Deliveries received after the last stocktake are added to the stock.</p>
          ${data.items.length ? html`<form class="form" id="delivery-form">
            <label>Product<select name="ingredient_id" required>
              ${data.items.map((i) => html`<option value="${i.id}">${i.name} (${i.unit})</option>`)}</select></label>
            <label>Quantity<input name="quantity" type="number" step="0.1" min="0.1" required></label>
            <label>Price per unit (€)<input name="unit_price" type="number" step="0.01" min="0" required></label>
            <label>Received on<input name="received_on" type="date" value="${data.as_of || ""}" required></label>
            <button type="submit">Record delivery</button>
          </form>` : html`<p class="muted">Assign products to this supplier before recording deliveries.</p>`}
        </section>
        <section class="card">
          <h2>Order history</h2>
          <p class="hint">Every delivery from this supplier, newest first.</p>
          ${data.purchases.length ? html`<table>
            <thead><tr><th>Date</th><th>Product</th><th class="num">Quantity</th><th class="num">Price</th><th class="num">Total</th></tr></thead>
            <tbody>${data.purchases.map((p) => html`
              <tr><td class="nowrap">${p.received_on}</td><td>${p.ingredient}</td><td class="num">${p.quantity} ${p.unit}</td>
                  <td class="num">${eur(p.unit_price)}</td><td class="num"><strong>${eur(p.total)}</strong></td></tr>`)}
            </tbody>
          </table>` : html`<p class="muted">No deliveries recorded yet.</p>`}
        </section>
      </div>
      <section class="card narrow" id="edit-supplier">
        <h2>Edit details</h2>
        <p class="hint">Every supplier needs a phone number or an email. To move a product to another supplier, edit the product.</p>
        <form class="form" id="supplier-form">
          <label>Name<input name="name" required minlength="2" maxlength="80" value="${sup.name}"></label>
          <label>Phone<input name="phone" value="${sup.phone || ""}" placeholder="+34 600 000 000"></label>
          <label>Email<input name="email" type="email" value="${sup.email || ""}" placeholder="orders@supplier.com"></label>
          <label>Delivery time (days)<input name="lead_time_days" type="number" min="0" max="60" value="${sup.lead_time_days}" required></label>
          <button type="submit">Save changes</button>
        </form>
      </section>`,
    after: (root) => {
      const delivery = root.querySelector("#delivery-form");
      if (delivery) {
        handleForm(delivery, {
          build: (f) => ({ ingredient_id: Number(f.ingredient_id.value), quantity: Number(f.quantity.value),
                           unit_price: Number(f.unit_price.value), received_on: f.received_on.value }),
          send: (body) => api("sales", `/sales/suppliers/${supplierId}/purchases`, { method: "POST", body }),
          done: () => { flash("Delivery recorded."); location.reload(); },
        });
      }
      handleForm(root.querySelector("#supplier-form"), {
        build: (f) => ({ name: f.name.value.trim(), phone: textOrNull(f.phone.value), email: textOrNull(f.email.value),
                         lead_time_days: Number(f.lead_time_days.value) }),
        send: (body) => api("sales", `/sales/suppliers/${supplierId}`, { method: "PUT", body }),
        done: (answer) => { flash(`“${answer.name}” updated.`); location.reload(); },
      });
    },
  };
});