/* Staff: the roles and employees a manager creates, edits and deletes, and shifts the clock-in system
 * missed. Everything here is personnel's own data, so it works even when sales is down. */
"use strict";

const staffPage = startPage({
  title: "Staff",
  intro: "The roles in the restaurant and the people in each one. Hourly rates drive payroll; diners per hour " +
         "and minimum staff drive the recommended schedule.",
});

function showSuccess(message) {
  document.getElementById("page-flash").innerHTML = piece(notice("success", message));
}

function roleForm(roles) {
  return html`
    <section class="card" id="role-card">
      <h2 id="role-form-title">Add a role</h2>
      <p class="hint">A job in the restaurant. Diners per hour: how many guests one person in this role can serve in an hour.</p>
      <form class="form" id="role-form">
        <input type="hidden" name="editing">
        <div class="inline-fields">
          <label>Name<input name="name" required minlength="2" maxlength="60" placeholder="Sommelier"></label>
          <label>Hourly rate (€)<input name="hourly_rate" type="number" step="0.01" min="0.01" max="200" required></label>
          <label>Diners per hour<input name="covers_per_hour" type="number" min="1" max="500" required></label>
          <label>Minimum staff<input name="min_staff" type="number" min="0" max="50" value="0" required></label>
        </div>
        <div class="row-actions" style="justify-content:flex-start">
          <button type="submit">Add role</button>
          <button type="button" class="button" id="role-cancel" hidden>Cancel</button>
        </div>
      </form>
    </section>
    <section class="card">
      <h2>Roles</h2>
      <p class="hint">A role can only be deleted when nobody has it.</p>
      ${roles.length ? html`<table>
        <thead><tr><th>Role</th><th class="num">Rate</th><th class="num">Diners / hour</th><th class="num">Minimum</th>
                   <th class="num">People</th><th></th></tr></thead>
        <tbody>${roles.map((r) => html`
          <tr><td>${r.name}</td><td class="num">${eur(r.hourly_rate)}</td><td class="num">${r.covers_per_hour}</td>
              <td class="num">${r.min_staff}</td><td class="num">${r.employees}</td>
              <td><div class="row-actions">
                <button type="button" class="button" data-edit-role="${r.id}">Edit</button>
                <button type="button" class="button danger" data-delete-role="${r.id}" ${r.employees ? raw("disabled title=\"Give its employees another role first\"") : ""}>Delete</button>
              </div></td></tr>`)}
        </tbody>
      </table>` : html`<p class="muted">No roles yet. Add the first one above.</p>`}
    </section>`;
}

function employeeForms(employees, roles) {
  const roleOptions = roles.map((r) => html`<option value="${r.id}">${r.name}</option>`);
  return html`
    <div class="split">
      <section class="card" id="employee-card">
        <h2 id="employee-form-title">Add an employee</h2>
        <p class="hint">Their pay is their clocked hours × the hourly rate of their role.</p>
        ${roles.length ? html`<form class="form" id="employee-form">
          <input type="hidden" name="editing">
          <label>Name<input name="name" required minlength="2" maxlength="80" placeholder="Ana Ruiz"></label>
          <label>Role<select name="role_id" required><option value="">Choose…</option>${roleOptions}</select></label>
          <div class="row-actions" style="justify-content:flex-start">
            <button type="submit">Add employee</button>
            <button type="button" class="button" id="employee-cancel" hidden>Cancel</button>
          </div>
        </form>` : html`<p class="muted">Add a role first.</p>`}
      </section>
      <section class="card" id="shift-card">
        <h2>Record a missed shift</h2>
        <p class="hint">When the clock-in system missed someone's shift. It counts in payroll and the schedule at once.
          Shifts cannot overlap, last more than 16 hours or be on a future day.</p>
        ${employees.length ? html`<form class="form" id="shift-form">
          <label>Employee<select name="employee_id" required><option value="">Choose…</option>
            ${employees.map((e) => html`<option value="${e.id}">${e.name} (${e.role})</option>`)}</select></label>
          <div class="inline-fields">
            <label>Clocked in<input name="clock_in" type="datetime-local" required></label>
            <label>Clocked out<input name="clock_out" type="datetime-local" required></label>
          </div>
          <button type="submit">Record shift</button>
        </form>` : html`<p class="muted">Add an employee first.</p>`}
      </section>
    </div>
    <section class="card">
      <h2>Employees</h2>
      <p class="hint">Someone added by mistake can be deleted while they have no clock-ins; after that they are part of payroll.</p>
      ${employees.length ? html`<table>
        <thead><tr><th>Employee</th><th>Role</th><th class="num">Clock-ins</th><th></th></tr></thead>
        <tbody>${employees.map((e) => html`
          <tr><td>${e.name}</td><td class="muted">${e.role}</td><td class="num">${e.clock_ins}</td>
              <td><div class="row-actions">
                <button type="button" class="button" data-edit-employee="${e.id}">Edit</button>
                <button type="button" class="button danger" data-delete-employee="${e.id}" ${e.clock_ins ? raw("disabled title=\"Has clock-ins, which payroll uses\"") : ""}>Delete</button>
              </div></td></tr>`)}
        </tbody>
      </table>` : html`<p class="muted">No employees yet.</p>`}
    </section>`;
}

/* Puts a form in "edit" mode for one row, or back to "add" mode. */
function editMode(form, title, addLabel, item) {
  const cancel = form.querySelector("button.button");
  form.editing.value = item ? item.id : "";
  document.getElementById(title.id).textContent = item ? `Edit ${item.name}` : title.add;
  form.querySelector("button[type=submit]").textContent = item ? "Save changes" : addLabel;
  cancel.hidden = !item;
  if (!item) form.reset();
}

function load() {
  mount(staffPage, async () => {
    const [roles, employees] = await Promise.all([api("personnel", "/personnel/roles"), api("personnel", "/personnel/employees")]);
    return { html: html`${roleForm(roles)}${employeeForms(employees, roles)}`, after: () => wire(roles, employees) };
  });
}

function wire(roles, employees) {
  const roleFormEl = document.getElementById("role-form");
  const roleTitle = { id: "role-form-title", add: "Add a role" };
  handleForm(roleFormEl, {
    build: (f) => ({ id: f.editing.value, body: { name: f.name.value.trim(), hourly_rate: Number(f.hourly_rate.value),
                     covers_per_hour: Number(f.covers_per_hour.value), min_staff: Number(f.min_staff.value) } }),
    send: ({ id, body }) => id ? api("personnel", `/personnel/roles/${id}`, { method: "PUT", body })
                               : api("personnel", "/personnel/roles", { method: "POST", body }),
    done: (answer) => { showSuccess(`Role “${answer.name}” saved.`); load(); },
  });
  document.getElementById("role-cancel").addEventListener("click", () => editMode(roleFormEl, roleTitle, "Add role", null));
  document.querySelectorAll("[data-edit-role]").forEach((button) => button.addEventListener("click", () => {
    const role = roles.find((r) => String(r.id) === button.dataset.editRole);
    editMode(roleFormEl, roleTitle, "Add role", role);
    ["name", "hourly_rate", "covers_per_hour", "min_staff"].forEach((field) => { roleFormEl[field].value = role[field]; });
    roleFormEl.scrollIntoView({ behavior: "smooth", block: "center" });
  }));
  document.querySelectorAll("[data-delete-role]").forEach((button) => button.addEventListener("click", () =>
    remove(`/personnel/roles/${button.dataset.deleteRole}`, roles.find((r) => String(r.id) === button.dataset.deleteRole).name)));

  const employeeFormEl = document.getElementById("employee-form");
  if (employeeFormEl) {
    const employeeTitle = { id: "employee-form-title", add: "Add an employee" };
    handleForm(employeeFormEl, {
      build: (f) => ({ id: f.editing.value, body: { name: f.name.value.trim(), role_id: Number(f.role_id.value) } }),
      send: ({ id, body }) => id ? api("personnel", `/personnel/employees/${id}`, { method: "PUT", body })
                                 : api("personnel", "/personnel/employees", { method: "POST", body }),
      done: (answer) => { showSuccess(`Employee “${answer.name}” saved.`); load(); },
    });
    document.getElementById("employee-cancel").addEventListener("click", () => editMode(employeeFormEl, employeeTitle, "Add employee", null));
    document.querySelectorAll("[data-edit-employee]").forEach((button) => button.addEventListener("click", () => {
      const person = employees.find((e) => String(e.id) === button.dataset.editEmployee);
      editMode(employeeFormEl, employeeTitle, "Add employee", person);
      employeeFormEl.name.value = person.name;
      employeeFormEl.role_id.value = person.role_id;
      employeeFormEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }));
  }
  document.querySelectorAll("[data-delete-employee]").forEach((button) => button.addEventListener("click", () =>
    remove(`/personnel/employees/${button.dataset.deleteEmployee}`,
           employees.find((e) => String(e.id) === button.dataset.deleteEmployee).name)));

  const shiftForm = document.getElementById("shift-form");
  if (shiftForm) {
    handleForm(shiftForm, {
      // datetime-local gives "2026-09-10T12:00", local time without a zone, which is what personnel expects
      build: (f) => ({ employee_id: Number(f.employee_id.value), clock_in: f.clock_in.value, clock_out: f.clock_out.value }),
      send: (body) => api("personnel", "/personnel/clock-ins", { method: "POST", body }),
      done: (answer) => { showSuccess(`Shift of ${num(answer.hours, 2)} hours recorded. It is already in payroll.`); load(); },
    });
  }
}

async function remove(path, name) {
  if (!window.confirm(`Delete ${name}? This cannot be undone.`)) return;
  try {
    await api("personnel", path, { method: "DELETE" });
    showSuccess(`“${name}” deleted.`);
    load();
  } catch (error) {
    if (!(error instanceof SessionExpired)) document.getElementById("page-flash").innerHTML = piece(notice("error", error.message));
  }
}

load();