(function () {
  "use strict";

  var CANALES = ["WhatsApp", "App de domicilio", "Instagram", "Facebook", "Llamada"];
  var MEDIOS = ["Transferencia", "Nequi", "Daviplata", "Efectivo"];
  var COL = { "WhatsApp": "#1f9d55", "App de domicilio": "#e8590c", "Instagram": "#b5179e", "Facebook": "#1c6ed6", "Llamada": "#6b665a" };
  var TABS = {
    "Administrador": [["enc", "Pedidos"], ["coc", "Cocina"], ["dom", "Reparto"], ["caja", "Caja"]],
    "Cajera": [["enc", "Pedidos"], ["coc", "Cocina"], ["dom", "Reparto"]],
    "Auxiliar de Cocina": [["coc", "Cocina"]],
    "Domiciliario": [["dom", "Reparto"]]
  };
  var S = { user: null, view: null, pedidos: [], resumen: null, rep: null, payload: null };
  var timer = null;

  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function money(n) { return "$" + Number(n || 0).toLocaleString("es-CO"); }
  function opts(a) { return a.map(function (x) { return "<option>" + esc(x) + "</option>"; }).join(""); }
  var toastT;
  function toast(m) { var t = $("toast"); t.textContent = m; t.classList.add("on"); clearTimeout(toastT); toastT = setTimeout(function () { t.classList.remove("on"); }, 3800); }

  async function api(path, o) {
    o = o || {};
    var h = { "Content-Type": "application/json", "X-CSRFToken": csrf() };
    var r = await fetch("/api" + path, { method: o.method || "GET", headers: h, credentials: "same-origin", body: o.body ? JSON.stringify(o.body) : undefined });
    var d = await r.json().catch(function () { return {}; });
    if (r.status === 401 && S.user) { salir(); }
    if (!r.ok) { var e = new Error(d.error || "Error del servidor"); e.status = r.status; e.data = d; throw e; }
    return d;
  }

  /* ---------- Sesión ---------- */
  function csrf() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }
  function salir() {
    var habia = S.user;
    clearInterval(timer);
    S = { user: null, view: null, pedidos: [], resumen: null, rep: null, payload: null };
    renderLogin();
    if (habia) fetch("/api/logout", { method: "POST", headers: { "X-CSRFToken": csrf() }, credentials: "same-origin" });
  }
  function renderLogin() {
    $("app").innerHTML = '<div class="login"><aside class="login-brand"><img src="/static/pedidos/logo-claro.png" alt=""><h2>PedidoCentral</h2><p>Cocina oculta El Cairo</p></aside>' +
      '<section class="login-box"><h1>Entra a tu turno</h1><p class="sub">Usa el usuario y la clave que te dio el administrador.</p>' +
      '<form id="lf"><label for="u">Usuario</label><input id="u" autocomplete="username" required>' +
      '<label for="pw">Clave</label><input id="pw" type="password" autocomplete="current-password" required>' +
      '<button class="btn big" type="submit">Entrar</button></form></section></div>';
    $("u").focus();
  }

  async function entrar() {
    try {
      var d = await api("/login", { method: "POST", body: { username: $("u").value.trim(), password: $("pw").value } });
      S.user = d.usuario; iniciar();
    } catch (e) { toast(e.message); }
  }
  function iniciar() {
    S.view = TABS[S.user.rol][0][0];
    var ini = String(S.user.nombre || "?").trim().charAt(0).toUpperCase();
    $("app").innerHTML =
      '<header class="top"><div class="in"><div class="logo"><img src="/static/pedidos/logo-claro.png" alt="PedidoCentral"><div><b>PedidoCentral</b><small>Cocina oculta El Cairo</small></div></div><div class="sp"></div>' +
      '<div class="me"><span class="av" aria-hidden="true">' + esc(ini) + '</span><div><b>' + esc(S.user.nombre) + '</b><span>' + esc(S.user.rol) + '</span></div><button class="btn sm ghost" data-a="salir">Salir</button></div></div></header>' +
      '<div class="wrap"><div class="stats" id="stats"></div><nav class="tabs" id="tabs"></nav><main id="main"></main></div>';
    renderTabs(); renderMain(); refresh(true);
    clearInterval(timer); timer = setInterval(function () { refresh(false); }, 15000);
  }

  /* ---------- Datos ---------- */
  function typing() {
    var a = document.activeElement;
    return !!(a && /INPUT|TEXTAREA|SELECT/.test(a.tagName) && a.closest("#lista,#cols,#caja"));
  }
  async function refresh(force) {
    if (!S.user) return;
    try {
      var r = await Promise.all([api("/pedidos"), api("/resumen"), S.view === "caja" ? api("/reportes") : null]);
      S.pedidos = r[0]; S.resumen = r[1]; if (r[2]) S.rep = r[2];
      renderStats(); renderTabs();
      if (force || !typing()) fill();
    } catch (e) { if (e.status !== 401) toast(e.message); }
  }
  async function mover(accion, id, body) {
    try { await api("/pedidos/" + id + "/" + accion, { method: "PATCH", body: body || {} }); await refresh(true); }
    catch (e) { toast(e.message); }
  }

  /* ---------- Vistas ---------- */
  function renderStats() {
    var r = S.resumen || {};
    var t = [["Por enviar a cocina", r.porEnviar, "reg"], ["En cocina", r.enCocina, "coc"], ["En reparto", r.enReparto, "ruta"]];
    if (r.ventasHoy != null) t.push(["Ventas de hoy", money(r.ventasHoy), "ventas"]);
    $("stats").innerHTML = t.map(function (s) { return '<div class="stat t-' + s[2] + '"><b>' + (s[1] == null ? 0 : s[1]) + "</b><span>" + s[0] + "</span></div>"; }).join("");
  }
  function pendientes(v) {
    return S.pedidos.filter(function (o) {
      if (v === "enc") return o.estado === "Registrado";
      if (v === "coc") return o.estado === "En Cocina" && o.estadoPreparacion === "Pendiente";
      if (v === "dom") return (o.estado === "En Cocina" && o.estadoPreparacion === "Listo") || o.estado === "En Ruta";
      return false;
    }).length;
  }
  function renderTabs() {
    $("tabs").innerHTML = TABS[S.user.rol].map(function (t) {
      var n = pendientes(t[0]);
      return '<button class="' + (S.view === t[0] ? "on" : "") + '" data-a="tab" data-v="' + t[0] + '">' + t[1] + (n ? ' <span class="badge">' + n + "</span>" : "") + "</button>";
    }).join("");
  }

  function renderMain() {
    var m = $("main");
    if (S.view === "enc") {
      m.innerHTML = '<div class="grid"><section class="panel">' + formHtml() + '</section><section class="panel"><h2>Pedidos de hoy <span class="count" id="cnt">0</span></h2><div id="lista"></div></section></div>';
      addLine();
    } else if (S.view === "caja") m.innerHTML = '<div id="caja"></div>';
    else m.innerHTML = '<div class="cols" id="cols"></div>';
    fill();
  }
  function fill() {
    if (S.view === "enc") {
      $("cnt").textContent = S.pedidos.length;
      $("lista").innerHTML = S.pedidos.length ? S.pedidos.map(card).join("") : '<p class="empty">Aún no hay pedidos. Registra el primero con el formulario.</p>';
    } else if (S.view === "coc") {
      $("cols").innerHTML =
        col("En preparación", sel("En Cocina", "Pendiente"), "No hay pedidos en cocina.", "coc") +
        col("Listos para recoger", sel("En Cocina", "Listo"), "Nada esperando al domiciliario.", "ok");
    } else if (S.view === "dom") {
      $("cols").innerHTML =
        col("Listos para recoger", sel("En Cocina", "Listo"), "Aún no hay pedidos listos.", "ok") +
        col("En camino", sel("En Ruta"), "No hay entregas en curso.", "ruta");
    } else if (S.view === "caja") cajaHtml();
  }
  function sel(estado, prep) {
    return S.pedidos.filter(function (o) { return o.estado === estado && (!prep || o.estadoPreparacion === prep); })
      .sort(function (a, b) { return b.minutos - a.minutos; });
  }
  function col(t, arr, vacio, tono) {
    return '<section class="panel lane t-' + tono + '"><h2>' + t + ' <span class="count">' + arr.length + "</span></h2>" + (arr.length ? arr.map(card).join("") : '<p class="empty">' + vacio + "</p>") + "</section>";
  }

  var ICO = {
    pin: '<path d="M12 21s-7-6.2-7-11a7 7 0 1 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    tel: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
    nota: '<path d="M5 4h14v12l-4 4H5z"/><path d="M15 20v-4h4"/>',
    pago: '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M3 10h18"/>'
  };
  function ico(n) { return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICO[n] + "</svg>"; }
  var PASOS = ["Pago", "Cocina", "Listo", "Ruta", "Entrega"];

  function estadoTxt(o) {
    if (o.estado === "Cancelado") return "Cancelado";
    if (o.estado === "Entregado") return "Entregado";
    if (o.estado === "En Ruta") return "En camino" + (o.domiciliario ? " con " + o.domiciliario : "");
    if (o.estado === "En Cocina") return o.estadoPreparacion === "Listo" ? "Listo para recoger" : "En preparación";
    return o.pagoValidado ? "Pago validado, listo para enviar a cocina" : o.urlComprobante ? "Comprobante por validar" : "Esperando comprobante de pago";
  }
  function tono(o) {
    if (o.estado === "Cancelado") return "off";
    if (o.estado === "Entregado") return "ok";
    if (o.estado === "En Ruta") return "ruta";
    if (o.estado === "En Cocina") return o.estadoPreparacion === "Listo" ? "ok" : "coc";
    return "reg";
  }
  function paso(o) {
    if (o.estado === "Entregado") return 4;
    if (o.estado === "En Ruta") return 3;
    if (o.estado === "En Cocina") return o.estadoPreparacion === "Listo" ? 2 : 1;
    return 0;
  }
  function btn(a, txt, id, cls) { return '<button class="btn sm ' + (cls || "") + '" data-a="' + a + '" data-id="' + id + '">' + txt + "</button>"; }

  function card(o) {
    var rol = S.user.rol, caja = rol === "Cajera" || rol === "Administrador", coc = rol === "Auxiliar de Cocina" || rol === "Administrador";
    var mio = o.idDomiciliario == null || o.idDomiciliario === S.user.id;
    var cocLate = o.estado === "En Cocina" && o.estadoPreparacion === "Pendiente" && o.minutosCocina >= 20;
    var sinAtender = o.estado === "Registrado" && o.minutos >= 10;
    var late = cocLate || sinAtender, off = o.estado === "Cancelado";
    var when = cocLate ? "¡Más de 20 min en cocina! (" + o.minutosCocina + " min)" : (sinAtender ? "¡Sin atender! " : "") + "Hace " + o.minutos + " min";
    var b = "", pagoBox = "";

    if (caja && o.estado === "Registrado") {
      if (!o.pagoValidado && !o.urlComprobante) pagoBox = '<div class="pago">' + btn("foto", "Subir foto del pago", o.id) + "</div>";
      else if (!o.pagoValidado) b += btn("validar-pago", "Validar pago", o.id, "ok") + btn("foto", "Cambiar foto", o.id, "sec");
      else b += btn("enviar-cocina", "Enviar a cocina", o.id);
    }
    if (coc && o.estado === "En Cocina" && o.estadoPreparacion === "Pendiente") b += btn("listo", "Marcar listo", o.id);
    if (rol === "Domiciliario") {
      if (o.estado === "En Cocina" && o.estadoPreparacion === "Listo" && mio) b += btn("retirar", "Salir a entregar", o.id);
      if (o.estado === "En Ruta" && o.idDomiciliario === S.user.id) b += btn("entregar", "Marcar entregado", o.id, "ok");
    }
    if (caja && (o.estado === "Registrado" || o.estado === "En Cocina")) b += btn("cancelar", "Cancelar", o.id, "sec");

    var items = o.items.map(function (i) { return '<li><span class="q">' + i.cantidad + '×</span><span class="p">' + esc(i.producto) + '</span><span class="m">' + money(i.subtotal) + "</span></li>"; }).join("");
    var link = /^https?:\/\//i.test(o.urlComprobante || "");
    var imgFoto = (o.urlComprobante || "").indexOf("/api/comprobantes/") === 0
      ? '<a class="foto" href="' + esc(o.urlComprobante) + '" target="_blank" rel="noopener"><img src="' + esc(o.urlComprobante) + '" alt="Foto del comprobante de pago" loading="lazy"></a>' : "";
    var pago = '<div class="mt">' + ico("pago") + "<span>" + esc(o.medioPago || "Sin medio de pago") + ' <em class="mini ' + (o.pagoValidado ? "ok" : "warn") + '">' + (o.pagoValidado ? "Validado" : "Por validar") + "</em>" +
      (link ? ' <a href="' + esc(o.urlComprobante) + '" target="_blank" rel="noopener noreferrer">Ver comprobante</a>' : "") + "</span></div>";
    var p = paso(o);
    var prog = off ? "" : '<ol class="track">' + PASOS.map(function (n, k) { return '<li class="' + (k <= p ? "f" : "") + (k === p ? " cur" : "") + '"><i></i>' + n + "</li>"; }).join("") + "</ol>";

    return '<article class="ticket t-' + tono(o) + (late ? " late" : "") + (off ? " off" : "") + '" style="--ch:' + (COL[o.canal] || "#6b665a") + '"><div class="tb">' +
      '<div class="th"><span class="num">#' + o.id + '</span><span class="chip"><i></i>' + esc(o.canal) + "</span></div>" +
      '<div class="who">' + esc(o.nombre) + '</div><div class="state"><span class="pill">' + esc(estadoTxt(o)) + "</span></div>" +
      '<ul class="items">' + items + '</ul><div class="total"><span>Total</span><span>' + money(o.total) + "</span></div>" +
      '<div class="mt">' + ico("pin") + "<span>" + esc(o.direccion) + "</span></div>" +
      '<div class="mt">' + ico("tel") + "<span>" + esc(o.telefono) + "</span></div>" +
      (o.notas ? '<div class="mt">' + ico("nota") + "<span>" + esc(o.notas) + "</span></div>" : "") +
      pago + imgFoto + pagoBox + prog + "</div>" +
      '<div class="tf"><span class="when' + (late ? " l" : "") + '">' + when + "</span>" + (b ? '<span class="row" style="margin:0">' + b + "</span>" : "") + "</div></article>";
  }

  /* ---------- Formulario de pedido ---------- */
  function formHtml() {
    return '<h2>Nuevo pedido</h2><form id="f" autocomplete="off">' +
      '<div class="two"><div><label for="canal">Canal</label><select id="canal">' + opts(CANALES) + '</select></div><div><label for="medio">Medio de pago</label><select id="medio">' + opts(MEDIOS) + "</select></div></div>" +
      '<label for="nombre">Nombre del cliente</label><input id="nombre" required maxlength="100">' +
      '<label for="tel">Teléfono</label><input id="tel" inputmode="tel" required maxlength="40">' +
      '<label for="dir">Dirección</label><input id="dir" required maxlength="200">' +
      '<label>Productos (cantidad · producto · subtotal)</label><div id="lines"></div><button type="button" class="link" data-a="addline">+ Agregar producto</button>' +
      '<div class="total"><span>Total</span><span id="tot">$0</span></div>' +
      '<label for="notas">Notas (opcional)</label><input id="notas" maxlength="300">' +
      '<label for="foto">Foto del pago (opcional)</label><input id="foto" type="file" accept="image/*">' +
      '<div id="alerta"></div><button class="btn big" type="submit" id="guardar">Guardar pedido</button></form>';
  }
  function addLine() {
    var d = document.createElement("div");
    d.className = "li";
    d.innerHTML = '<input class="q" type="number" min="1" max="99" value="1" aria-label="Cantidad"><input class="pr" placeholder="Producto" maxlength="100" aria-label="Producto"><input class="sb" type="number" min="0" step="500" placeholder="Subtotal" aria-label="Subtotal"><button type="button" data-a="quitar" aria-label="Quitar">×</button>';
    $("lines").appendChild(d);
  }
  function calcTotal() {
    var t = 0;
    [].forEach.call(document.querySelectorAll("#lines .sb"), function (i) { t += Number(i.value) || 0; });
    $("tot").textContent = money(t);
  }
  function leerForm() {
    var g = function (id) { return $(id).value.trim(); };
    var items = [].map.call(document.querySelectorAll("#lines .li"), function (l) {
      return { cantidad: l.querySelector(".q").value, producto: l.querySelector(".pr").value.trim(), subtotal: l.querySelector(".sb").value || 0 };
    }).filter(function (i) { return i.producto || Number(i.subtotal); });
    return { canal: g("canal"), medioPago: g("medio"), nombre: g("nombre"), telefono: g("tel"), direccion: g("dir"), notas: g("notas"), items: items };
  }
  async function guardar(p) {
    var b = $("guardar"); if (b) b.disabled = true;
    S.payload = p;
    try {
      var nuevo = await api("/pedidos", { method: "POST", body: p });
      var foto = S.foto; S.payload = null; S.foto = null;
      if (foto) {
        try { await subirFoto(nuevo.id, foto); toast("Pedido guardado con la foto del pago"); }
        catch (e2) { toast("Pedido guardado, pero la foto no se subió: " + e2.message); }
      } else toast("Pedido guardado");
      renderMain(); await refresh(true);
    } catch (e) {
      if (b) b.disabled = false;
      if (e.status === 409 && e.data && e.data.duplicado) {
        var d = e.data.duplicado;
        $("alerta").innerHTML = '<div class="warn"><b>Posible pedido duplicado.</b> Este teléfono ya tiene el pedido #' + d.id + " activo desde hace " + d.minutos + " min (" + esc(d.canal) + ').<div class="row"><button type="button" class="btn sm" data-a="forzar">Es otro pedido, guardar</button><button type="button" class="btn sm sec" data-a="revisar">Revisar</button></div></div>';
      } else toast(e.message);
    }
  }

  /* ---------- Foto del comprobante ---------- */
  var fg = document.createElement("input");
  fg.type = "file"; fg.accept = "image/*"; fg.hidden = true;
  document.body.appendChild(fg);
  fg.addEventListener("change", async function () {
    var f = fg.files[0], id = S.fotoPid;
    fg.value = "";
    if (!f || !id) return;
    try { toast("Subiendo foto…"); await subirFoto(id, f); toast("Foto guardada"); await refresh(true); }
    catch (e) { toast(e.message); }
  });
  function comprimir(file) {
    return new Promise(function (ok) {
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () {
        var k = Math.min(1, 1600 / Math.max(img.width, img.height));
        var c = document.createElement("canvas");
        c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
        var x = c.getContext("2d"); x.fillStyle = "#fff"; x.fillRect(0, 0, c.width, c.height); x.drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url);
        c.toBlob(function (b) { ok(b || file); }, "image/jpeg", 0.82);
      };
      img.onerror = function () { URL.revokeObjectURL(url); ok(file); };
      img.src = url;
    });
  }
  async function subirFoto(id, file) {
    var fd = new FormData();
    fd.append("foto", await comprimir(file), "comprobante.jpg");
    var r = await fetch("/api/pedidos/" + id + "/foto", { method: "POST", headers: { "X-CSRFToken": csrf() }, credentials: "same-origin", body: fd });
    var d = await r.json().catch(function () { return {}; });
    if (r.status === 401 && S.user) salir();
    if (!r.ok) throw new Error(d.error || "No se pudo subir la foto");
    return d;
  }

  /* ---------- Caja (solo administrador) ---------- */
  function tabla(cab, filas, vacio) {
    if (!filas.length) return '<p class="empty">' + vacio + "</p>";
    return "<table><thead><tr>" + cab.map(function (c, i) { return '<th class="' + (c[1] ? "n" : "") + '">' + c[0] + "</th>"; }).join("") + "</tr></thead><tbody>" + filas.join("") + "</tbody></table>";
  }
  function cajaHtml() {
    var r = S.rep; if (!r) { $("caja").innerHTML = '<p class="empty">Cargando…</p>'; return; }
    var mx = function (a, k) { return Math.max.apply(null, a.map(function (x) { return Number(x[k]) || 0; }).concat(1)); };
    var bar = function (v, max, c) { return '<i class="bar" style="width:' + Math.round((Number(v) || 0) / max * 100) + "%" + (c ? ";background:" + c : "") + '"></i>'; };
    var md = mx(r.dias, "total"), mc = mx(r.canales, "ventas");
    $("caja").innerHTML = '<div class="cols">' +
      '<section class="panel"><h2>Ventas por día</h2>' + tabla([["Día"], ["Pedidos", 1], ["Total", 1]], r.dias.map(function (d) { return "<tr><td>" + esc(d.dia) + '</td><td class="n">' + d.pedidos + '</td><td class="n">' + money(d.total) + bar(d.total, md) + "</td></tr>"; }), "Aún no hay ventas con pago validado.") + "</section>" +
      '<section class="panel"><h2>Por canal</h2>' + tabla([["Canal"], ["Pedidos", 1], ["Ventas", 1]], r.canales.map(function (c) { return "<tr><td>" + esc(c.canal) + '</td><td class="n">' + c.pedidos + '</td><td class="n">' + money(c.ventas) + bar(c.ventas, mc, COL[c.canal]) + "</td></tr>"; }), "Sin pedidos.") + "</section>" +
      '<section class="panel"><h2>Sin pago validado <span class="count">' + r.sinPago.length + "</span></h2>" + tabla([["#"], ["Cliente"], ["Estado"], ["Total", 1]], r.sinPago.map(function (p) { return "<tr><td>" + p.id + "</td><td>" + esc(p.cliente) + "</td><td>" + esc(p.estado) + (p.tieneComprobante ? "" : " (sin comprobante)") + '</td><td class="n">' + money(p.total) + "</td></tr>"; }), "Todo el dinero está validado.") + "</section></div>";
  }

  /* ---------- Eventos ---------- */
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-a]"); if (!b) return;
    var a = b.dataset.a, id = b.dataset.id;
    if (a === "salir") return salir();
    if (a === "tab") { S.view = b.dataset.v; renderTabs(); renderMain(); return refresh(true); }
    if (a === "foto") { S.fotoPid = id; fg.click(); return; }
    if (a === "addline") return addLine();
    if (a === "quitar") { if (document.querySelectorAll("#lines .li").length > 1) b.parentNode.remove(); calcTotal(); return; }
    if (a === "forzar") { var p = S.payload; if (p) { p.forzar = true; guardar(p); } return; }
    if (a === "revisar") { $("alerta").innerHTML = ""; S.payload = null; return; }
    if (a === "comprobante") {
      var inp = document.querySelector('[data-c="' + id + '"]');
      return mover("comprobante", id, { urlComprobante: inp ? inp.value.trim() : "" });
    }
    if (a === "cancelar") { if (!confirm("¿Cancelar el pedido #" + id + "?")) return; }
    mover(a, id);
  });
  document.addEventListener("input", function (ev) { if (ev.target.closest && ev.target.closest(".li")) calcTotal(); });
  document.addEventListener("submit", function (ev) {
    ev.preventDefault();
    if (ev.target.id === "lf") entrar();
    else if (ev.target.id === "f") { var ff = $("foto"); S.foto = ff && ff.files[0] ? ff.files[0] : null; guardar(leerForm()); }
  });

  /* ---------- Inicio ---------- */
  api("/yo").then(function (u) { if (TABS[u.rol]) { S.user = u; iniciar(); } else renderLogin(); })
    .catch(function () { renderLogin(); });
})();