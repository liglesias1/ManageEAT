/* Payroll: hours and pay of every employee over the period with clock-ins. Only personnel's own data. */
"use strict";

const payrollPage = startPage({ title: "Payroll" });

mount(payrollPage, async () => {
  const data = await api("personnel", "/personnel/payroll");
  setHeading("Payroll", html`Hours each employee clocked and what they are owed, from ${data.start || "–"} to ${data.end || "–"}.
    Pay = clocked hours × the hourly rate of the employee's role. Extra hours are paid at the same rate.`);
  return {
    html: html`
      ${kpis([
        { icon: "payroll", label: "Total labour cost", value: eur(data.total_pay), note: "Wages for the whole period" },
        { icon: "clock", label: "Hours worked", value: num(data.total_hours), note: "Clocked by all employees" },
        { icon: "staff", label: "Employees", value: data.payroll.length, note: "With at least one shift" },
        { icon: "trend", label: "Average cost per hour", value: eur(data.total_hours ? data.total_pay / data.total_hours : 0),
          note: "Across all roles" },
      ])}
      <div class="split">
        <section class="card">
          <h2>Cost by role</h2>
          <p class="hint">Where the wage bill goes.</p>
          <div class="chart-box small"><canvas id="role-chart"></canvas></div>
          <table>
            <thead><tr><th>Role</th><th class="num">People</th><th class="num">Hours</th><th class="num">Pay</th></tr></thead>
            <tbody>${data.by_role.map((r) => html`
              <tr><td>${r.role}</td><td class="num">${r.people}</td><td class="num">${num(r.hours)}</td><td class="num">${eur(r.pay)}</td></tr>`)}
            </tbody>
          </table>
        </section>
        <section class="card">
          <h2>Employees</h2>
          <p class="hint">Grouped by role. <a class="link" href="staff.html">Add an employee or a missed shift →</a></p>
          ${data.payroll.length ? html`<table>
            <thead><tr><th>Employee</th><th>Role</th><th class="num">Shifts</th><th class="num">Hours</th>
                       <th class="num">Rate</th><th class="num">Pay</th></tr></thead>
            <tbody>${data.payroll.map((p) => html`
              <tr><td>${p.employee}</td><td class="muted">${p.role}</td><td class="num">${p.shifts}</td>
                  <td class="num">${num(p.hours, 1)}</td><td class="num">${eur(p.hourly_rate)}</td>
                  <td class="num"><strong>${eur(p.pay)}</strong></td></tr>`)}
            </tbody>
          </table>` : html`<p class="muted">No clock-ins recorded yet.</p>`}
        </section>
      </div>`,
    after: () => {
      if (!data.by_role.length) return;
      new Chart(document.getElementById("role-chart"), {
        type: "bar",
        data: {
          labels: data.by_role.map((r) => r.role),
          datasets: [{ data: data.by_role.map((r) => r.pay), backgroundColor: "#7d2633", borderRadius: 6 }],
        },
        options: {
          indexAxis: "y",
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => eur(c.raw) } } },
          scales: { x: { ticks: { callback: (v) => "€" + v.toLocaleString() } } },
        },
      });
    },
  };
});