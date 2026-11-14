<<<<<<< HEAD
# PedidoCentral · Cocina oculta El Cairo (Django)

Proyecto Django 5.2 sobre MySQL 8. Usa tu base `pedidocentral` tal cual (tablas, triggers y procedimientos del `.sql`); Django se conecta a esas tablas y la interfaz web consume una API JSON del mismo proyecto.

## Estructura
```
config/            settings.py, urls.py, wsgi.py
pedidos/models.py  modelos que mapean las tablas del .sql (managed = False)
pedidos/views.py   API: login por rol, pedidos, acciones, resumen y reportes
pedidos/urls.py    rutas
pedidos/templates  index.html (pantalla única)
pedidos/static     app.js y styles.css (interfaz)
pedidos/management/commands/claves.py   asigna claves a los usuarios demo
database/          pedidocentral.sql y ajustes.sql
```

## 1. Base de datos (MySQL 8)
```bash
mysql -u root -p < database/pedidocentral.sql
mysql -u root -p pedidocentral < database/ajustes.sql
```
`ajustes.sql` es necesario: agrega los 5 canales y el estado Cancelado, y permite cancelar pedidos.

## 2. Ejecutar
```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # Linux/Mac: cp .env.example .env  (completa DB_USER y DB_PASSWORD)
python manage.py claves TuClave123
python manage.py runserver
```
Abre http://127.0.0.1:8000 e ingresa con `cajera`, `cocina`, `domi` o `admin`.
No hace falta `migrate`: las tablas las crea el `.sql` y las sesiones van en una cookie firmada.

## 3. Flujo de un pedido (las reglas las aplica la base de datos)
1. **Cajera** registra el pedido → `Registrado`.
2. Pega el enlace del comprobante y pulsa **Validar pago** (RF-03).
3. **Enviar a cocina** → `En Cocina`; el temporizador pasa a rojo a los 20 min (RF-04).
4. **Cocina** pulsa **Marcar listo**.
5. **Domiciliario**: **Salir a entregar** → `En Ruta` y luego **Marcar entregado**.
6. Cancelar solo antes de salir a reparto. Todo queda en `historial_estado_pedido`.

## 4. API (requiere sesión y el encabezado `X-CSRFToken` en POST/PATCH)
| Método | Ruta | Rol |
|---|---|---|
| POST | `/api/login`, `/api/logout` | — |
| GET | `/api/yo`, `/api/pedidos`, `/api/resumen`, `/api/pedidos/<id>/historial` | todos |
| POST | `/api/pedidos` (409 si hay duplicado; reenviar con `"forzar": true`) | Cajera, Admin |
| PATCH | `/api/pedidos/<id>/comprobante`, `validar-pago`, `enviar-cocina`, `cancelar` | Cajera, Admin |
| PATCH | `/api/pedidos/<id>/listo` | Cocina, Admin |
| PATCH | `/api/pedidos/<id>/retirar`, `entregar` | Domiciliario |
| GET | `/api/reportes` | Admin |

## 5. Publicar (Render, Railway...)
- Variables: `DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` (con `https://`), y las `DB_*` de una base MySQL en la nube (revisa que permita triggers y procedimientos almacenados).
- Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- Inicio: `gunicorn config.wsgi`
- Nunca subas `.env` a GitHub. Cambia las claves de los usuarios demo.
=======
# Pedido_central
>>>>>>> origin/main
