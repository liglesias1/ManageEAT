/* Managers: everyone who can log in to this restaurant, and the form to add one. */
"use strict";

const managersPage = startPage({
  title: "Managers",
  intro: "Everyone who can log in to this restaurant. Each manager has their own email and password and sees the same data.",
});

mount(managersPage, async () => {
  const managers = await api("personnel", "/account/managers");
  const me = session.get();
  setHeading(`Managers of ${me.restaurant.name}`);
  return {
    html: html`
      <div class="split">
        <section class="card">
          <h2>Managers</h2>
          <p class="hint">${managers.length} with access.</p>
          <table>
            <thead><tr><th>Name</th><th>Email</th></tr></thead>
            <tbody>${managers.map((m) => html`
              <tr><td>${m.name}${m.id === me.user.id ? html` <span class="badge new">You</span>` : ""}</td><td>${m.email}</td></tr>`)}
            </tbody>
          </table>
        </section>
        <section class="card" id="new-manager">
          <h2>Add a manager</h2>
          <p class="hint">They log in with their own email and password. Share the password with them in person.</p>
          <form class="form" id="manager-form">
            <label>Name<input name="name" required minlength="2" maxlength="80"></label>
            <label>Email<input name="email" type="email" required autocomplete="off"></label>
            <label>Password <span class="muted">(at least 8 characters)</span>
              <input name="password" type="password" required minlength="8" autocomplete="new-password"></label>
            <button type="submit">Add manager</button>
          </form>
        </section>
      </div>`,
    after: (root) => handleForm(root.querySelector("#manager-form"), {
      build: (f) => ({ name: f.name.value.trim(), email: f.email.value.trim(), password: f.password.value }),
      send: (body) => api("personnel", "/account/managers", { method: "POST", body }),
      done: (answer) => { flash(`Manager “${answer.name}” added.`); location.reload(); },
    }),
  };
});