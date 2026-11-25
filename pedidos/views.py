import json
import logging
import re
from functools import wraps

from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.db import DatabaseError, connection, transaction
from django.http import JsonResponse
from django.middleware.csrf import rotate_token
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import Cliente, DetallePedido, Pago, Pedido, Usuario

log = logging.getLogger(__name__)

CANALES = ["WhatsApp", "App de domicilio", "Instagram", "Facebook", "Llamada"]
MEDIOS = ["Transferencia", "Nequi", "Daviplata", "Efectivo", "Datáfono"]
VENTANA_DUPLICADO_MIN = 20  # NEC-01
ADMIN, CAJA, COCINA, DOMI = "Administrador", "Cajera", "Auxiliar de Cocina", "Domiciliario"


class HttpErr(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.msg, self.status = msg, status


def err(msg, status=400):
    return JsonResponse({"error": msg}, status=status)


def api(roles=(), metodos=("GET",), publico=False):
    """Revisa método, sesión y rol, y convierte los errores de la base de datos en respuestas JSON.
    Las reglas de negocio (RF-03, RF-05, CU-04...) las lanzan los triggers con SIGNAL 45000 (error 1644)."""
    def deco(fn):
        @wraps(fn)
        def inner(request, *a, **k):
            if request.method not in metodos:
                return err("Método no permitido", 405)
            if not publico:
                u = request.session.get("u")
                if not u:
                    return err("Inicia sesión", 401)
                if roles and u["rol"] not in roles:
                    return err("Tu rol no puede hacer esto", 403)
                request.u = u
            try:
                return fn(request, *a, **k)
            except HttpErr as e:
                return err(e.msg, e.status)
            except DatabaseError as e:
                code = e.args[0] if e.args else None
                if code == 1644:
                    return err(str(e.args[1]), 409)
                if code == 1062:
                    return err("Registro duplicado", 409)
                log.exception("Error de base de datos")
                return err("Error interno del servidor", 500)
        return inner
    return deco


def cuerpo(request):
    try:
        d = json.loads(request.body or b"{}")
    except ValueError:
        raise HttpErr("JSON inválido")
    return d if isinstance(d, dict) else {}


def filas(sql, params=()):
    with connection.cursor() as cur:
        cur.execute(sql, list(params))  # siempre con lista: los % literales van como %%
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def llamar(procedimiento, params):
    with connection.cursor() as cur:
        cur.callproc(procedimiento, params)


def limpiar(v, mx):
    return str("" if v is None else v).strip()[:mx]


def entero(v, defecto=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return defecto


# ---------------------------------------------------------------- Pantalla y sesión
@ensure_csrf_cookie
def index(request):
    return render(request, "pedidos/index.html")


@api(publico=True)
def salud(request):
    filas("SELECT 1")
    return JsonResponse({"ok": True})


@api(publico=True, metodos=("POST",))
def login(request):
    clave_cache = "login:" + request.META.get("REMOTE_ADDR", "?")
    n = cache.get(clave_cache, 0)
    if n >= 8:
        raise HttpErr("Demasiados intentos, espera un minuto", 429)
    cache.set(clave_cache, n + 1, 60)

    b = cuerpo(request)
    u = Usuario.objects.select_related("rol").filter(username=str(b.get("username", "")), activo=True).first()
    if u and u.password_hash == "CAMBIAR_POR_HASH":
        raise HttpErr("Este usuario aún no tiene clave. Ejecuta: python manage.py claves TuClave123", 403)
    if not u or not check_password(str(b.get("password", "")), u.password_hash):
        raise HttpErr("Usuario o clave incorrectos", 401)

    usuario = {"id": u.id, "nombre": u.nombre, "rol": u.rol.nombre}
    request.session.cycle_key()
    request.session["u"] = usuario
    rotate_token(request)
    return JsonResponse({"usuario": usuario})


@api(publico=True, metodos=("POST",))
def logout(request):
    request.session.flush()
    return JsonResponse({"ok": True})


@api()
def yo(request):
    return JsonResponse(request.u)


# ---------------------------------------------------------------- Consultas
SELECT = """
  SELECT p.idPedido AS id, p.canal, p.estado, p.total, p.direccionEntrega AS direccion, p.observaciones AS notas,
         DATE_FORMAT(p.fechaHora, '%%H:%%i') AS hora,
         TIMESTAMPDIFF(MINUTE, p.fechaHora, NOW()) AS minutos,
         cl.nombre, cl.telefono,
         pg.medioPago, pg.urlComprobante, COALESCE(pg.validado, 0) AS pagoValidado,
         c.estadoPreparacion,
         TIMESTAMPDIFF(MINUTE, c.fechaInicio, COALESCE(c.fechaListo, NOW())) AS minutosCocina,
         ds.idDomiciliario, u.nombre AS domiciliario
    FROM pedido p
    JOIN cliente cl ON cl.idCliente = p.idCliente
    LEFT JOIN pago pg ON pg.idPedido = p.idPedido
    LEFT JOIN comanda_kds c ON c.idPedido = p.idPedido
    LEFT JOIN despacho ds ON ds.idPedido = p.idPedido
    LEFT JOIN usuario u ON u.idUsuario = ds.idDomiciliario"""


def listar(where="", params=(), limite=300):
    rows = filas(f"{SELECT} {'WHERE ' + where if where else ''} ORDER BY p.fechaHora DESC LIMIT %s", [*params, limite])
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    det = filas(
        "SELECT idPedido, producto, cantidad, subtotal FROM detalle_pedido WHERE idPedido IN (%s) ORDER BY idDetalle"
        % ",".join(["%s"] * len(ids)), ids)
    for r in rows:
        r["total"] = int(r["total"])
        r["minutos"] = int(r["minutos"])
        r["minutosCocina"] = None if r["minutosCocina"] is None else int(r["minutosCocina"])
        r["pagoValidado"] = bool(r["pagoValidado"])
        r["items"] = [{"producto": d["producto"], "cantidad": d["cantidad"], "subtotal": int(d["subtotal"])}
                      for d in det if d["idPedido"] == r["id"]]
    return rows


def _normalizar_medio(valor):
    m = limpiar(valor, 30)
    if m.lower() in ("datafono", "datáfono"):
        return "Datáfono"
    for item in MEDIOS:
        if item.lower() == m.lower():
            return item
    return m or "Transferencia"


def _componer_observaciones(d):
    extras = []
    total_items = sum(i["subtotal"] for i in d["items"])
    if d["medio"] == "Efectivo" and d["montoEfectivo"] > 0:
        vueltas = d["montoEfectivo"] - total_items
        extras.append(
            f"Efectivo: paga con ${d['montoEfectivo']:,}"
            + (f" (cambio: ${vueltas:,})" if vueltas >= 0 else " (monto menor al subtotal)")
        )
    elif d["medio"] == "Datáfono" and d["refPago"]:
        extras.append(f"Datáfono ref/tarjeta: {d['refPago']}")
    elif d["medio"] in ("Transferencia", "Nequi", "Daviplata") and d["refPago"]:
        extras.append(f"Ref. pago: {d['refPago']}")

    partes = [p for p in [d["notas"], *extras] if p]
    return limpiar(" | ".join(partes), 300) or None


def validar(b):
    items = b.get("items") if isinstance(b.get("items"), list) else []
    d = {
        "canal": limpiar(b.get("canal"), 40),
        "nombre": limpiar(b.get("nombre"), 100),
        "telefono": re.sub(r"\D", "", limpiar(b.get("telefono"), 40)),
        "direccion": limpiar(b.get("direccion"), 200),
        "notas": limpiar(b.get("notas"), 300),
        "medio": _normalizar_medio(b.get("medioPago")),
        "url": limpiar(b.get("urlComprobante"), 500),
        "montoEfectivo": entero(b.get("montoEfectivo"), 0),
        "refPago": limpiar(b.get("refPago"), 80),
        "items": [{"producto": limpiar(i.get("producto"), 100), "cantidad": entero(i.get("cantidad")),
                   "subtotal": entero(i.get("subtotal"))} for i in items[:30] if isinstance(i, dict)],
    }
    e = []
    if d["canal"] not in CANALES: e.append("canal inválido")
    if not d["nombre"]: e.append("el nombre es obligatorio")
    if not 7 <= len(d["telefono"]) <= 20: e.append("teléfono inválido")
    if not d["direccion"]: e.append("la dirección es obligatoria")
    if d["medio"] not in MEDIOS: e.append("medio de pago inválido")
    if d["url"] and not re.match(r"^https?://", d["url"], re.I): e.append("el comprobante debe ser un enlace http(s)")
    if not d["items"]: e.append("agrega al menos un producto")
    if any(not i["producto"] or not 1 <= i["cantidad"] <= 99 or not 0 <= i["subtotal"] <= 10_000_000 for i in d["items"]):
        e.append("revisa producto, cantidad y subtotal de cada línea")
    return d, e


# ---------------------------------------------------------------- Pedidos
@api()
def lista(request):
    return JsonResponse(listar("p.estado NOT IN ('Entregado','Cancelado') OR DATE(p.fechaHora) = CURDATE()"), safe=False)


@api((CAJA, ADMIN), ("POST",))
def crear(request):
    b = cuerpo(request)
    d, errores = validar(b)
    if errores:
        raise HttpErr("; ".join(errores))

    if b.get("forzar") is not True:
        rep = listar("p.estado NOT IN ('Entregado','Cancelado') AND cl.telefono = %s "
                     "AND p.fechaHora > NOW() - INTERVAL %s MINUTE", [d["telefono"], VENTANA_DUPLICADO_MIN], 1)
        if rep:
            return JsonResponse({"error": "Posible pedido duplicado", "duplicado": rep[0]}, status=409)

    with transaction.atomic():
        cliente, _ = Cliente.objects.update_or_create(
            telefono=d["telefono"], defaults={"nombre": d["nombre"], "direccion": d["direccion"]})
        obs = _componer_observaciones(d)
        ped = Pedido.objects.create(
            cliente=cliente, usuario_cajera_id=request.u["id"], canal=d["canal"],
            direccion_entrega=d["direccion"], observaciones=obs)
        DetallePedido.objects.bulk_create(
            [DetallePedido(pedido=ped, producto=i["producto"], cantidad=i["cantidad"], subtotal=i["subtotal"])
             for i in d["items"]])  # el trigger recalcula el total del pedido
        Pago.objects.create(pedido=ped, medio_pago=d["medio"], url_comprobante=d["url"] or None, validado=False)
    return JsonResponse(listar("p.idPedido = %s", [ped.id], 1)[0], status=201)


def pedidos(request):
    return (crear if request.method == "POST" else lista)(request)


# Cada acción llama a la base de datos, que aplica las reglas de negocio.
def _comprobante(request, pid):
    url = limpiar(cuerpo(request).get("urlComprobante"), 500)
    if not re.match(r"^https?://", url, re.I):
        raise HttpErr("Pega un enlace http(s) al comprobante")
    if not Pago.objects.filter(pedido_id=pid, validado=False).update(url_comprobante=url):
        raise HttpErr("El pago no existe o ya fue validado", 409)


def _validar_pago(request, pid):
    pg = Pago.objects.filter(pedido_id=pid).first()
    if not pg:
        raise HttpErr("El pedido no tiene pago registrado", 404)
    llamar("sp_validar_pago", [pg.id, request.u["id"]])


def _enviar_cocina(request, pid):
    llamar("sp_enviar_a_cocina", [pid, request.u["id"]])


def _listo(request, pid):
    c = filas("SELECT idComanda FROM comanda_kds WHERE idPedido = %s", [pid])
    if not c:
        raise HttpErr("El pedido no está en cocina", 409)
    llamar("sp_marcar_listo", [c[0]["idComanda"]])


def _despachador(pid):
    ds = filas("SELECT idDomiciliario FROM despacho WHERE idPedido = %s", [pid])
    return ds[0]["idDomiciliario"] if ds else None


def _retirar(request, pid):
    uid, actual = request.u["id"], _despachador(pid)
    if actual is None:
        llamar("sp_asignar_domiciliario", [pid, uid])
    elif actual != uid:
        raise HttpErr("Este pedido ya lo tiene otro domiciliario", 409)
    llamar("sp_retirar_pedido", [pid, uid])


def _entregar(request, pid):
    if _despachador(pid) != request.u["id"]:
        raise HttpErr("Este pedido no está asignado a ti", 409)
    llamar("sp_marcar_entregado", [pid, request.u["id"]])


def _cancelar(request, pid):
    with connection.cursor() as cur:
        cur.execute("SET @idUsuarioActual = %s", [request.u["id"]])  # lo usa el trigger del historial
        cur.execute("UPDATE pedido SET estado = 'Cancelado' WHERE idPedido = %s AND estado IN ('Registrado','En Cocina')", [pid])
        if cur.rowcount == 0:
            raise HttpErr("Solo se puede cancelar antes de salir a reparto", 409)


ACCIONES = {
    "comprobante": ((CAJA, ADMIN), _comprobante),
    "validar-pago": ((CAJA, ADMIN), _validar_pago),
    "enviar-cocina": ((CAJA, ADMIN), _enviar_cocina),
    "listo": ((COCINA, ADMIN), _listo),
    "retirar": ((DOMI,), _retirar),
    "entregar": ((DOMI,), _entregar),
    "cancelar": ((CAJA, ADMIN), _cancelar),
}


@api(metodos=("PATCH",))
def accion(request, pid, nombre):
    if nombre not in ACCIONES:
        raise HttpErr("Ruta no encontrada", 404)
    roles, fn = ACCIONES[nombre]
    if request.u["rol"] not in roles:
        raise HttpErr("Tu rol no puede hacer esto", 403)
    fn(request, pid)
    ped = listar("p.idPedido = %s", [pid], 1)
    if not ped:
        raise HttpErr("Pedido no encontrado", 404)
    return JsonResponse(ped[0])


@api()
def historial(request, pid):
    return JsonResponse(filas(
        """SELECT h.estadoAnterior, h.estadoNuevo, DATE_FORMAT(h.fechaHora, '%%d/%%m %%H:%%i') AS fecha, u.nombre AS usuario
             FROM historial_estado_pedido h LEFT JOIN usuario u ON u.idUsuario = h.idUsuario
            WHERE h.idPedido = %s ORDER BY h.idHistorial""", [pid]), safe=False)


# ---------------------------------------------------------------- Resumen y reportes
@api()
def resumen(request):
    r = filas(
        """SELECT COALESCE(SUM(p.estado = 'Registrado'), 0) AS porEnviar,
                  COALESCE(SUM(p.estado = 'En Cocina' AND c.estadoPreparacion = 'Pendiente'), 0) AS enCocina,
                  COALESCE(SUM((p.estado = 'En Cocina' AND c.estadoPreparacion = 'Listo') OR p.estado = 'En Ruta'), 0) AS enReparto,
                  COALESCE(SUM(CASE WHEN DATE(p.fechaHora) = CURDATE() AND p.estado <> 'Cancelado' AND pg.validado = 1
                                    THEN p.total END), 0) AS ventasHoy
             FROM pedido p
             LEFT JOIN comanda_kds c ON c.idPedido = p.idPedido
             LEFT JOIN pago pg ON pg.idPedido = p.idPedido""")[0]
    return JsonResponse({
        "porEnviar": int(r["porEnviar"]), "enCocina": int(r["enCocina"]), "enReparto": int(r["enReparto"]),
        "ventasHoy": int(r["ventasHoy"]) if request.u["rol"] == ADMIN else None,
    })


@api((ADMIN,))
def reportes(request):
    dias = filas("SELECT DATE_FORMAT(dia, '%%d/%%m/%%Y') AS dia, pedidos, totalVendido FROM v_ventas_diarias ORDER BY v_ventas_diarias.dia DESC LIMIT 14")
    canales = filas("SELECT canal, COUNT(*) AS pedidos, COALESCE(SUM(total), 0) AS ventas FROM pedido WHERE estado <> 'Cancelado' GROUP BY canal ORDER BY ventas DESC")
    sin_pago = filas("SELECT idPedido AS id, cliente, total, estado, medioPago, tieneComprobante FROM v_pedidos_sin_pago_validado ORDER BY fechaHora DESC LIMIT 50")
    return JsonResponse({
        "dias": [{"dia": r["dia"], "pedidos": int(r["pedidos"]), "total": int(r["totalVendido"])} for r in dias],
        "canales": [{"canal": r["canal"], "pedidos": int(r["pedidos"]), "ventas": int(r["ventas"])} for r in canales],
        "sinPago": [{**r, "total": int(r["total"]), "tieneComprobante": bool(r["tieneComprobante"])} for r in sin_pago],
    })
