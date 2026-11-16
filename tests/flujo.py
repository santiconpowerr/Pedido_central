"""Prueba de humo del flujo completo de PedidoCentral contra una base MySQL REAL.

ATENCION: BORRA todos los pedidos, clientes y pagos de la base. Por seguridad solo corre si el
nombre de la base contiene "test". Uso (desde la raiz del proyecto):

        sed 's/pedidocentral/pedidocentral_test/g' database/pedidocentral.sql | mysql -u root -p
    sed 's/pedidocentral/pedidocentral_test/g' database/ajustes.sql | mysql -u root -p pedidocentral_test
    DB_NAME=pedidocentral_test python tests/flujo.py

Nota: pedidocentral.sql hace CREATE DATABASE/USE pedidocentral; para la base de pruebas cambia ese
nombre en una copia del archivo (sed 's/pedidocentral/pedidocentral_test/g').
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
if "test" not in os.environ.get("DB_NAME", "pedidocentral").lower():
    sys.exit("Por seguridad esta prueba borra datos y solo corre en una base cuyo nombre contenga 'test' (DB_NAME=pedidocentral_test).")
import django; django.setup()
from django.core.management import call_command
call_command("claves", "TuClave123", verbosity=0)
from django.core.cache import cache; cache.clear()
from django.test import Client
from django.db import connection

PASS = FAIL = 0
def check(nombre, cond, extra=""):
    global PASS, FAIL
    if cond: PASS += 1; print("  OK   ", nombre)
    else: FAIL += 1; print("  FALLA", nombre, extra)

def cliente(user):
    c = Client(enforce_csrf_checks=False, raise_request_exception=False)
    r = c.post("/api/login", json.dumps({"username": user, "password": "TuClave123"}), content_type="application/json", REMOTE_ADDR="10.0.0.%d" % (hash(user) % 200 + 1))
    assert r.status_code == 200, (user, r.status_code, r.content[:200])
    return c

def j(r): return json.loads(r.content)
def patch(c, path, body=None): return c.patch(path, json.dumps(body or {}), content_type="application/json")

with connection.cursor() as cur:
    cur.execute("DELETE FROM historial_estado_pedido"); cur.execute("DELETE FROM despacho"); cur.execute("DELETE FROM comanda_kds")
    cur.execute("DELETE FROM pago"); cur.execute("DELETE FROM detalle_pedido"); cur.execute("DELETE FROM pedido"); cur.execute("DELETE FROM cliente")

caja, cocina, domi, admin = cliente("cajera"), cliente("cocina"), cliente("domi"), cliente("admin")
def nuevo(tel, medio, url=""):
    r = caja.post("/api/pedidos", json.dumps({"canal": "WhatsApp", "nombre": "Cliente " + tel, "telefono": tel, "direccion": "Calle 1", "medioPago": medio,
        "urlComprobante": url, "items": [{"producto": "Hamburguesa", "cantidad": 2, "subtotal": 30000}]}), content_type="application/json")
    return r, (j(r) if r.status_code == 201 else None)

print("\n[1] Flujo normal con transferencia")
r, p = nuevo("3001110001", "Transferencia", "https://x.co/c1"); check("crear pedido", r.status_code == 201, r.content)
pid = p["id"]
check("validar pago", patch(caja, f"/api/pedidos/{pid}/validar-pago").status_code == 200)
check("enviar a cocina", patch(caja, f"/api/pedidos/{pid}/enviar-cocina").status_code == 200)
check("marcar listo", patch(cocina, f"/api/pedidos/{pid}/listo").status_code == 200)
check("domi retira", patch(domi, f"/api/pedidos/{pid}/retirar").status_code == 200)
check("domi entrega", patch(domi, f"/api/pedidos/{pid}/entregar").status_code == 200)

print("\n[2] BUG 1: pedido en EFECTIVO sin comprobante")
r, p = nuevo("3001110002", "Efectivo"); check("crear pedido efectivo", r.status_code == 201, r.content)
pid = p["id"]
r = patch(caja, f"/api/pedidos/{pid}/validar-pago"); check("validar pago efectivo sin comprobante", r.status_code == 200, f"{r.status_code} {r.content[:120]}")
r = patch(caja, f"/api/pedidos/{pid}/enviar-cocina"); check("efectivo pasa a cocina", r.status_code == 200, f"{r.status_code} {r.content[:120]}")
r2, p2 = nuevo("3001110003", "Transferencia")
r = patch(caja, f"/api/pedidos/{p2['id']}/validar-pago"); check("transferencia SIN comprobante sigue rechazada", r.status_code == 409, f"{r.status_code}")

print("\n[3] BUG 2: fallo en retirar no debe dejar domiciliario asignado")
r, p = nuevo("3001110004", "Transferencia", "https://x.co/c4"); pid = p["id"]
patch(caja, f"/api/pedidos/{pid}/validar-pago"); patch(caja, f"/api/pedidos/{pid}/enviar-cocina"); patch(cocina, f"/api/pedidos/{pid}/listo")
with connection.cursor() as cur:  # sabotaje: fuerza que el UPDATE a 'En Ruta' falle (estado inconsistente)
    cur.execute("CREATE TRIGGER trg_sabotaje BEFORE UPDATE ON despacho FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'sabotaje'")
r = patch(domi, f"/api/pedidos/{pid}/retirar"); check("retirar falla (esperado)", r.status_code >= 400, str(r.status_code))
with connection.cursor() as cur:
    cur.execute("DROP TRIGGER trg_sabotaje"); cur.execute("SELECT COUNT(*) FROM despacho WHERE idPedido=%s", [pid]); n = cur.fetchone()[0]
check("no queda despacho huerfano", n == 0, f"despachos={n}")
r = patch(domi, f"/api/pedidos/{pid}/retirar"); check("reintento de retirar funciona", r.status_code == 200, f"{r.status_code} {r.content[:120]}")

print("\n[4] Otro domiciliario no puede quitarle el pedido")
with connection.cursor() as cur:
    cur.execute("SELECT idUsuario FROM usuario WHERE username='admin'"); adm = cur.fetchone()[0]
r = patch(admin, f"/api/pedidos/{pid}/retirar"); check("admin (no domi) no puede retirar", r.status_code == 403, str(r.status_code))

print("\n[5] Zona horaria de la conexion")
with connection.cursor() as cur:
    cur.execute("SELECT @@session.time_zone, TIMESTAMPDIFF(HOUR, UTC_TIMESTAMP(), NOW())"); tz, dif = cur.fetchone()
check("sesion en hora de Colombia (UTC-5)", dif == -5, f"tz={tz} diferencia_vs_UTC={dif}h")

print("\n[6] entero() con 1e999")
r = caja.post("/api/pedidos", json.dumps({"canal": "WhatsApp", "nombre": "X", "telefono": "3001110009", "direccion": "d", "medioPago": "Efectivo",
    "items": [{"producto": "a", "cantidad": 1, "subtotal": "1e999"}]}), content_type="application/json")
check("subtotal 1e999 -> 400 (no 500)", r.status_code == 400, str(r.status_code))

print("\n[7] Login: errores y limite")
c = Client(raise_request_exception=False)
for i in range(3): c.post("/api/login", json.dumps({"username": "cajera", "password": "mala"}), content_type="application/json", REMOTE_ADDR="9.9.9.9")
r = c.post("/api/login", json.dumps({"username": "cajera", "password": "TuClave123"}), content_type="application/json", REMOTE_ADDR="9.9.9.9")
check("login correcto despues de 3 fallos", r.status_code == 200, str(r.status_code))
r = c.post("/api/login", json.dumps({"username": "noexiste", "password": "x"}), content_type="application/json", REMOTE_ADDR="9.9.9.8")
r2 = c.post("/api/login", json.dumps({"username": "cajera", "password": "x"}), content_type="application/json", REMOTE_ADDR="9.9.9.7")
check("usuario inexistente y clave mala dan el mismo mensaje", j(r)["error"] == j(r2)["error"])

print("\n[7b] Limite de intentos por usuario (no bloquea a los demas)")
c = Client(raise_request_exception=False)
for i in range(9): c.post("/api/login", json.dumps({"username": "domi", "password": "mala"}), content_type="application/json", REMOTE_ADDR="8.8.8.8")
r = c.post("/api/login", json.dumps({"username": "domi", "password": "TuClave123"}), content_type="application/json", REMOTE_ADDR="8.8.8.8")
check("tras 9 fallos, 'domi' queda limitado (429)", r.status_code == 429, str(r.status_code))
r = c.post("/api/login", json.dumps({"username": "cajera", "password": "TuClave123"}), content_type="application/json", REMOTE_ADDR="8.8.8.8")
check("'cajera' desde la misma IP sigue entrando", r.status_code == 200, str(r.status_code))

print("\n[8] Cabecera anti-clickjacking")
r = Client(raise_request_exception=False).get("/"); check("X-Frame-Options presente", r.headers.get("X-Frame-Options") in ("DENY", "SAMEORIGIN"), str(r.headers.get("X-Frame-Options")))

print(f"\nRESULTADO: {PASS} ok, {FAIL} fallas"); sys.exit(1 if FAIL else 0)
