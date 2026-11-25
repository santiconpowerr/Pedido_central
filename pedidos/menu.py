"""
Menú público de El Cairo (se ve en /menu).

PARA CAMBIAR EL MENÚ: edita solo este archivo, guarda, haz commit y push; Render lo publica solo.
  - Cada categoría es un bloque con su nombre y su lista de platos.
  - "precio" va en pesos, sin puntos ni signo: 18000 se muestra como $18.000.
  - "descripcion" es opcional (ingredientes, tamaño...). Déjala en "" si no la quieres.
  - "disponible": False muestra el plato como "Agotado" sin borrarlo. Si no lo pones, se asume True.

IMPORTANTE: los precios de abajo salen de los pedidos de ejemplo de la base de datos
(hamburguesa sencilla 18.000, doble 24.000, perro caliente 12.000, picada para 2 38.000).
Cámbialos por los reales y agrega los demás productos.
"""

# Número de WhatsApp de la tienda con indicativo y sin signos, por ejemplo "573001234567".
# Si lo dejas vacío, el botón "Pedir por WhatsApp" no aparece.
WHATSAPP = ""

MENU = [
    {
        "categoria": "Hamburguesas",
        "platos": [
            {"nombre": "Hamburguesa sencilla", "descripcion": "", "precio": 18000},
            {"nombre": "Hamburguesa doble", "descripcion": "", "precio": 24000},
        ],
    },
    {
        "categoria": "Perros calientes",
        "platos": [
            {"nombre": "Perro caliente", "descripcion": "", "precio": 12000},
        ],
    },
    {
        "categoria": "Para compartir",
        "platos": [
            {"nombre": "Picada para 2", "descripcion": "", "precio": 38000},
        ],
    },
]