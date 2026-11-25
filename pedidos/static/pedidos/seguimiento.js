(function () {
  "use strict";
  var REFRESCO_MS = 30000;
  var $ = function (id) { return document.getElementById(id); };
  var form = $("form"), btn = $("btn"), err = $("error"), res = $("resultado");
  var timer = null;

  // Si el enlace trae ?pedido=123, el número ya viene escrito.
  var params = new URLSearchParams(location.search);
  var pre = (params.get("pedido") || "").replace(/\D/g, "").slice(0, 10);
  if (pre) { $("pedido").value = pre; $("telefono").focus(); } else { $("pedido").focus(); }

  function mostrarError(msg) { err.textContent = msg; err.hidden = !msg; }

  function pintar(d) {
    var est = $("estado");
    est.className = "estado" + (d.cancelado ? " cancelado" : d.paso === 3 ? " ok" : d.paso === 2 ? " salio" : "");
    $("titulo").textContent = d.titulo;
    $("detalle").textContent = d.detalle;
    $("num").textContent = "#" + d.pedido;

    var ol = $("pasos"); ol.innerHTML = "";
    if (!d.cancelado) {
      d.pasos.forEach(function (p, i) {
        var li = document.createElement("li");
        if (i < d.paso || d.paso === 3) li.className = "hecho";
        else if (i === d.paso) li.className = "actual";
        var n = document.createElement("span"); n.textContent = p.nombre; li.appendChild(n);
        if (p.hora && i <= d.paso) {
          var h = document.createElement("span"); h.className = "hora"; h.textContent = p.hora; li.appendChild(h);
        }
        ol.appendChild(li);
      });
    }
    var ul = $("items"); ul.innerHTML = "";
    d.items.forEach(function (it) {
      var li = document.createElement("li");
      li.textContent = it.cantidad + " × " + it.producto;
      ul.appendChild(li);
    });
    var final = d.cancelado || d.paso === 3;
    $("nota").textContent = final ? "" : "Esta página se actualiza sola cada 30 segundos.";
    res.hidden = false;
    return final;
  }

  function consultar(silencioso) {
    var token = form.querySelector("[name=csrfmiddlewaretoken]").value;
    if (!silencioso) { btn.disabled = true; mostrarError(""); }
    return fetch("/api/seguimiento", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": token },
      credentials: "same-origin",
      body: JSON.stringify({ pedido: $("pedido").value, telefono: $("telefono").value })
    }).then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, d: d }; });
    }).then(function (x) {
      if (!x.ok) {
        clearTimeout(timer);
        if (!silencioso) res.hidden = true;
        mostrarError(x.d.error || "No se pudo consultar. Intenta de nuevo.");
        return;
      }
      mostrarError("");
      clearTimeout(timer);
      if (!pintar(x.d)) timer = setTimeout(function () { consultar(true); }, REFRESCO_MS);
    }).catch(function () {
      if (!silencioso) mostrarError("No hay conexión. Intenta de nuevo.");
      else timer = setTimeout(function () { consultar(true); }, REFRESCO_MS);
    }).then(function () { btn.disabled = false; });
  }

  form.addEventListener("submit", function (e) { e.preventDefault(); consultar(false); });
})();