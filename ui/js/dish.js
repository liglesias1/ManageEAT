/* Edit dish: change the name, type, price or recipe of one dish; its code stays the same. */
"use strict";

const dishPage = startPage({ title: "Edit dish" });
const dishCode = queryParam("code") || "";

mount(dishPage, async () => {
  const [dish, menu] = await Promise.all([
    api("sales", `/sales/dishes/${encodeURIComponent(dishCode)}`),
    api("sales", "/sales/dishes"),
  ]);
  setHeading(`Edit ${dish.name}`, html`Change the name, type, price or recipe of this dish. Its code (${dish.code}) stays the same,
    so its past sales are still linked to it. <a class="link" href="dishes.html">← Back to the menu</a>`);
  return {
    html: html`<section class="card">${dishForm({ categories: menu.categories, ingredients: menu.ingredients,
                                                    target: menu.target, dish, button: "Save changes" })}</section>`,
    after: (root) => setUpDishForm(root.querySelector(".dish-form"),
      (body) => api("sales", `/sales/dishes/${encodeURIComponent(dishCode)}`, { method: "PUT", body }),
      (answer) => {
        flash(`Dish “${answer.name}” updated.`);
        location.href = "dishes.html";
      }),
  };
});