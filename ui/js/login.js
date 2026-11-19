/* Login and register pages: both get a token from personnel and go on to the page that was asked for. */
"use strict";

function nextPage() {
  const next = queryParam("next") || "index.html";
  // Only a page of this site: never an address somewhere else that a crafted link could put here
  return /^[a-z-]+\.html(\?[\w=&%.-]*)?$/.test(next) ? next : "index.html";
}

const loginForm = document.getElementById("login-form");
if (loginForm) {
  handleForm(loginForm, {
    build: (form) => ({ email: form.email.value.trim(), password: form.password.value }),
    send: (body) => api("personnel", "/auth/login", { method: "POST", body }),
    done: (answer) => {
      session.save(answer);
      location.href = nextPage();
    },
  });
}

const registerForm = document.getElementById("register-form");
if (registerForm) {
  handleForm(registerForm, {
    build: (form) => ({
      restaurant_name: form.restaurant_name.value.trim(),
      name: form.name.value.trim(),
      email: form.email.value.trim(),
      password: form.password.value,
    }),
    send: (body) => api("personnel", "/auth/register", { method: "POST", body }),
    done: (answer) => {
      session.save(answer);
      flash(`Welcome to ManageEAT, ${answer.user.name}. Your restaurant starts empty: add your staff and menu.`);
      location.href = "index.html";
    },
  });
}