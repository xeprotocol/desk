/* The desk's page scripts. Everything goes through /v1 with the session cookie and the CSRF header;
   no forms post. Passkeys use the WebAuthn API with the base64url helpers below. */
(function () {
  "use strict";
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const csrf = () => (document.querySelector('meta[name="desk-csrf"]') || {}).content || "";

  async function api(method, path, body) {
    const r = await fetch(path, {
      method, credentials: "same-origin",
      headers: Object.assign({ "Accept": "application/json", "X-Desk-CSRF": csrf() }, body !== undefined ? { "Content-Type": "application/json" } : {}),
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try { data = await r.json(); } catch (e) { data = null; }
    if (!r.ok) throw new Error((data && (data.error || data.detail)) ? (data.error || JSON.stringify(data.detail)) : `${r.status} ${r.statusText}`);
    return data;
  }
  function say(el, text, ok) {
    if (!el) return;
    el.style.display = text ? "block" : "none";
    el.textContent = text || "";
    el.className = "msg " + (ok ? "ok" : "err");
  }
  const reload = () => location.reload();

  // ---- shell: theme, cog menu, mobile nav (as on the governance site) -------------------------
  const THEME_KEY = "xe-desk-theme";
  const theme = () => document.documentElement.dataset.theme === "light" ? "light" : "dark";
  function setTheme(t, animate) {
    const html = document.documentElement;
    if (animate && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      html.classList.add("g-theming"); setTimeout(() => html.classList.remove("g-theming"), 320);
    }
    html.dataset.theme = t;
    try { localStorage.setItem(THEME_KEY, t); } catch (e) {}
    const meta = document.querySelector('meta[name="theme-color"]'); if (meta) meta.content = t === "light" ? "#fafafa" : "#0a0a0a";
    $$("[data-theme-label]").forEach(el => { el.textContent = t === "dark" ? "Light theme" : "Dark theme"; });
  }
  document.addEventListener("DOMContentLoaded", () => {
    $$("[data-theme-label]").forEach(el => { el.textContent = theme() === "dark" ? "Light theme" : "Dark theme"; });
    const tt = $("#theme-toggle"); if (tt) tt.addEventListener("click", () => setTheme(theme() === "dark" ? "light" : "dark", true));
    const cog = $("#cog-menu"), pop = $("#cog-pop");
    if (cog && pop) {
      const close = () => { pop.hidden = true; cog.setAttribute("aria-expanded", "false"); };
      cog.addEventListener("click", e => { e.stopPropagation(); const open = pop.hidden; pop.hidden = !open; cog.setAttribute("aria-expanded", String(open)); });
      document.addEventListener("click", e => { if (!pop.hidden && !pop.contains(e.target)) close(); });
      document.addEventListener("keydown", e => { if (e.key === "Escape") close(); });
    }
    const nb = $("#nav-btn"), mn = $("#mobile-nav");
    if (nb && mn) nb.addEventListener("click", () => { mn.hidden = !mn.hidden; nb.setAttribute("aria-expanded", String(!mn.hidden)); });
  });

  // ---- base64url for WebAuthn -----------------------------------------------------------------
  const b64u = {
    enc: (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""),
    dec: (s) => { s = s.replace(/-/g, "+").replace(/_/g, "/"); s += "=".repeat((4 - s.length % 4) % 4); return Uint8Array.from(atob(s), c => c.charCodeAt(0)).buffer; },
  };
  function toCreationOptions(o) {
    const pk = Object.assign({}, o);
    pk.challenge = b64u.dec(o.challenge);
    pk.user = Object.assign({}, o.user, { id: b64u.dec(o.user.id) });
    if (o.excludeCredentials) pk.excludeCredentials = o.excludeCredentials.map(c => Object.assign({}, c, { id: b64u.dec(c.id) }));
    return pk;
  }
  function toRequestOptions(o) {
    const pk = Object.assign({}, o);
    pk.challenge = b64u.dec(o.challenge);
    if (o.allowCredentials) pk.allowCredentials = o.allowCredentials.map(c => Object.assign({}, c, { id: b64u.dec(c.id) }));
    return pk;
  }
  function credentialToJSON(c) {
    const r = c.response;
    const out = { id: c.id, rawId: b64u.enc(c.rawId), type: c.type, clientExtensionResults: c.getClientExtensionResults ? c.getClientExtensionResults() : {},
      authenticatorAttachment: c.authenticatorAttachment || undefined, response: { clientDataJSON: b64u.enc(r.clientDataJSON) } };
    if (r.attestationObject) {
      out.response.attestationObject = b64u.enc(r.attestationObject);
      if (r.getTransports) out.response.transports = r.getTransports();
    } else {
      out.response.authenticatorData = b64u.enc(r.authenticatorData);
      out.response.signature = b64u.enc(r.signature);
      if (r.userHandle) out.response.userHandle = b64u.enc(r.userHandle);
    }
    return out;
  }

  // ---- sign-in -------------------------------------------------------------------------------
  const loginForm = $("#login-form");
  if (loginForm) {
    const msg = $("#login-msg"), next = loginForm.dataset.next || "/";
    const go = () => { location.href = next.startsWith("/") ? next : "/"; };
    $("#passkey-login").addEventListener("click", async () => {
      try {
        if (!window.PublicKeyCredential) throw new Error("this browser has no passkey support; use the code");
        const email = $("#email").value.trim() || null;
        const begin = await api("POST", "/v1/auth/passkey/login/begin", { email });
        const cred = await navigator.credentials.get({ publicKey: toRequestOptions(begin.options) });
        await api("POST", "/v1/auth/passkey/login/finish", { challenge_id: begin.challenge_id, credential: credentialToJSON(cred) });
        go();
      } catch (e) { say(msg, e.message, false); }
    });
    $("#totp-login").addEventListener("click", async () => {
      try {
        await api("POST", "/v1/auth/totp/login", { email: $("#email").value.trim(), code: $("#code").value.trim() });
        go();
      } catch (e) { say(msg, e.message, false); }
    });
    $("#code").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); $("#totp-login").click(); } });
  }
  const inviteForm = $("#invite-form");
  if (inviteForm) {
    $("#accept-invite").addEventListener("click", async () => {
      try { await api("POST", "/v1/auth/invite/accept", { token: inviteForm.dataset.token }); location.href = "/team/account"; }
      catch (e) { say($("#invite-msg"), e.message, false); }
    });
  }

  // ---- account -------------------------------------------------------------------------------
  if ($("#add-passkey")) {
    $("#add-passkey").addEventListener("click", async () => {
      const msg = $("#passkey-msg");
      try {
        const begin = await api("POST", "/v1/auth/passkey/register/begin");
        const cred = await navigator.credentials.create({ publicKey: toCreationOptions(begin.options) });
        await api("POST", "/v1/auth/passkey/register/finish", { challenge_id: begin.challenge_id, credential: credentialToJSON(cred), label: $("#passkey-label").value.trim() });
        reload();
      } catch (e) { say(msg, e.message, false); }
    });
    $$("[data-remove-passkey]").forEach(b => b.addEventListener("click", async () => {
      if (!confirm("Remove this passkey?")) return;
      try { await api("DELETE", `/v1/auth/passkeys/${b.dataset.removePasskey}`); reload(); } catch (e) { say($("#passkey-msg"), e.message, false); }
    }));
  }
  const saveName = $("#save-name");
  if (saveName) saveName.addEventListener("click", async () => {
    saveName.disabled = true;
    try { await api("POST", "/v1/team/account/name", { name: $("#my-name").value.trim() }); say($("#name-msg"), "Saved.", true); setTimeout(reload, 500); }
    catch (e) { say($("#name-msg"), e.message, false); saveName.disabled = false; }
  });
  if ($("#setup-totp")) {
    let cid = null;
    $("#setup-totp").addEventListener("click", async () => {
      try {
        const r = await api("POST", "/v1/auth/totp/setup");
        cid = r.challenge_id; $("#totp-secret").textContent = r.secret; $("#totp-uri").href = r.uri;
        $("#totp-setup").style.display = "block"; $("#setup-totp").style.display = "none";
      } catch (e) { say($("#totp-msg"), e.message, false); }
    });
    $("#confirm-totp").addEventListener("click", async () => {
      try { await api("POST", "/v1/auth/totp/confirm", { challenge_id: cid, code: $("#totp-code").value.trim() }); reload(); }
      catch (e) { say($("#totp-msg"), e.message, false); }
    });
  }
  if ($("#remove-totp")) $("#remove-totp").addEventListener("click", async () => {
    try { await api("DELETE", "/v1/auth/totp"); reload(); } catch (e) { say($("#totp-msg"), e.message, false); }
  });
  if ($("#logout")) $("#logout").addEventListener("click", async () => { await api("POST", "/v1/auth/logout"); location.href = "/"; });

  // ---- tokens --------------------------------------------------------------------------------
  const tokenForm = $("#token-form");
  if (tokenForm) {
    tokenForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(tokenForm), msg = $("#token-msg");
      try {
        const r = await api("POST", "/v1/team/tokens", {
          model_id: fd.get("model_id"), label: fd.get("label") || "", days: parseInt(fd.get("days") || "90", 10),
          scopes: fd.getAll("scopes"), owner_id: fd.get("owner_id") ? parseInt(fd.get("owner_id"), 10) : null,
        });
        say(msg, `Token (shown once): ${r.token}`, true);
        msg.style.userSelect = "all";
      } catch (err) { say(msg, err.message, false); }
    });
    $$("[data-revoke]").forEach(b => b.addEventListener("click", async () => {
      if (!confirm("Revoke this token? Calls with it stop at once.")) return;
      try { await api("DELETE", `/v1/team/tokens/${b.dataset.revoke}`); reload(); } catch (e) { say($("#token-msg"), e.message, false); }
    }));
  }

  // ---- users ---------------------------------------------------------------------------------
  const userForm = $("#user-form");
  if (userForm) {
    userForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(userForm), msg = $("#user-msg");
      try {
        const u = await api("POST", "/v1/team/users", { email: fd.get("email"), name: fd.get("name") || "", roles: fd.getAll("roles") });
        const inv = await api("POST", `/v1/auth/invite/${u.id}`);
        say(msg, `Added. Invite link${inv.emailed ? " (also emailed)" : ""}: ${inv.url}`, true);
        msg.style.userSelect = "all";
      } catch (err) { say(msg, err.message, false); }
    });
  }
  $$("[data-invite]").forEach(b => b.addEventListener("click", async () => {
    try { const inv = await api("POST", `/v1/auth/invite/${b.dataset.invite}`); say($("#users-msg"), `Invite link${inv.emailed ? " (also emailed)" : ""}: ${inv.url}`, true); $("#users-msg").style.userSelect = "all"; }
    catch (e) { say($("#users-msg"), e.message, false); }
  }));
  $$("[data-rename]").forEach(el => el.addEventListener("click", async () => {
    const name = prompt("Name on this person's replies:", el.textContent.trim());
    if (name === null || !name.trim()) return;
    try { await api("PATCH", `/v1/team/users/${el.dataset.rename}`, { name: name.trim() }); reload(); }
    catch (e) { say($("#users-msg"), e.message, false); }
  }));
  $$("[data-toggle-active]").forEach(b => b.addEventListener("click", async () => {
    try { await api("PATCH", `/v1/team/users/${b.dataset.toggleActive}`, { active: b.dataset.active !== "true" }); reload(); }
    catch (e) { say($("#users-msg"), e.message, false); }
  }));

  // ---- ticket page ---------------------------------------------------------------------------
  const ticketEl = $(".ticket[data-ticket]");
  if (ticketEl) {
    const tid = ticketEl.dataset.ticket, facts = $("#facts"), fmsg = $("#facts-msg");
    const T = (p) => `/v1/team/tickets/${tid}${p}`;

    if ($("#edit-facts")) {
      $("#edit-facts").addEventListener("click", () => facts.classList.add("editing"));
      $("#cancel-facts").addEventListener("click", () => facts.classList.remove("editing"));
      $("#save-facts").addEventListener("click", async () => {
        const changes = {};
        $$("select.edit, input.edit", facts).forEach(el => {
          let v = el.value;
          if (el.name === "assignee_id") v = v ? parseInt(v, 10) : null;
          changes[el.name] = v === "" ? null : v;
        });
        try { await api("PATCH", T("/facts"), { changes }); reload(); } catch (e) { say(fmsg, e.message, false); }
      });
    }
    const statusSel = $("#status-select"), reasonSel = $("#closed-reason");
    if (statusSel) {
      statusSel.addEventListener("change", () => { reasonSel.style.display = statusSel.value === "closed" ? "" : "none"; });
      $("#set-status").addEventListener("click", async () => {
        const body = { status: statusSel.value };
        if (statusSel.value === "closed") body.closed_reason = reasonSel.value;
        if (statusSel.value === "disclosed" && !confirm("Disclose: the body leaves the vault and a public issue is opened. Continue?")) return;
        try { await api("POST", T("/status"), body); reload(); } catch (e) { say(fmsg, e.message, false); }
      });
    }
    if ($("#save-award")) {
      $("#save-award").addEventListener("click", async () => {
        const xe = parseFloat($("#award-xe").value);
        if (isNaN(xe)) return say(fmsg, "enter an amount in XE", false);
        try { await api("POST", T("/award"), { award_xe: Math.round(xe * 1e6) }); reload(); } catch (e) { say(fmsg, e.message, false); }
      });
      $("#approve-award").addEventListener("click", async () => {
        if (!confirm("Approve this award? It then appears on the leaderboard once the ticket is awarded.")) return;
        try { await api("POST", T("/award"), { approve: true }); reload(); } catch (e) { say(fmsg, e.message, false); }
      });
    }
    if ($("#convert-kind")) $("#convert-kind").addEventListener("click", async () => {
      const to = $("#convert-kind").dataset.to;
      if (!confirm(`Make this a ${to} ticket? The id and history stay.`)) return;
      try { await api("POST", T(`/kind?kind=${to}`)); reload(); } catch (e) { say(fmsg, e.message, false); }
    });
    if ($("#add-patch")) $("#add-patch").addEventListener("click", async () => {
      const ref = $("#patch-ref").value.trim();
      if (!ref) return;
      try { await api("POST", `/v1/tickets/${tid}/patch-refs`, { ref }); reload(); } catch (e) { say(fmsg, e.message, false); }
    });

    // reply
    const replyBody = $("#reply-body"), rmsg = $("#reply-msg");
    if (replyBody) {
      $$("[data-template]").forEach(b => b.addEventListener("click", async () => {
        try { const r = await api("GET", T(`/reply-template/${b.dataset.template}`)); replyBody.value = r.body; replyBody.focus(); }
        catch (e) { say(rmsg, e.message, false); }
      }));
      $("#send-reply").addEventListener("click", async () => {
        const body = replyBody.value.trim();
        if (!body) return say(rmsg, "write something first", false);
        if (!confirm("Send this reply in public?")) return;
        try { await api("POST", T("/replies"), { body }); reload(); } catch (e) { say(rmsg, e.message, false); }
      });
    }
    // notes
    if ($("#add-note")) $("#add-note").addEventListener("click", async () => {
      const body = $("#note-body").value.trim();
      if (!body) return;
      try { await api("POST", `/v1/tickets/${tid}/notes`, { body }); reload(); } catch (e) { say($("#note-msg"), e.message, false); }
    });
    // proposals
    $$("[data-adopt]").forEach(b => b.addEventListener("click", async () => {
      const card = b.closest(".proposal");
      try {
        const r = await api("POST", `/v1/team/proposals/${b.dataset.adopt}/adopt`, {});
        if (r.reply_draft !== undefined && replyBody) { replyBody.value = r.reply_draft; replyBody.focus(); card.classList.add("adopted"); b.disabled = true; }
        else reload();
      } catch (e) { say(fmsg, e.message, false); alert(e.message); }
    }));
    $$("[data-reject]").forEach(b => b.addEventListener("click", async () => {
      try { await api("POST", `/v1/team/proposals/${b.dataset.reject}/reject`, {}); reload(); } catch (e) { alert(e.message); }
    }));
    if ($("#adopt-all")) $("#adopt-all").addEventListener("click", async () => {
      const ids = $$("[data-adopt]:not([disabled])").filter(b => b.closest(".proposal").dataset.field !== "reply_draft").map(b => parseInt(b.dataset.adopt, 10));
      if (!ids.length || !confirm(`Adopt ${ids.length} proposals?`)) return;
      try { await api("POST", "/v1/team/proposals/bulk", { adopt: ids }); reload(); } catch (e) { alert(e.message); }
    });
  }
})();
