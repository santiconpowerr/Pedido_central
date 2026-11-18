from django.urls import path

from . import views

urlpatterns = [
    path("", views.index),
    path("api/salud", views.salud),
    path("api/login", views.login),
    path("api/logout", views.logout),
    path("api/yo", views.yo),
    path("api/pedidos", views.pedidos),
    path("api/pedidos/<int:pid>/historial", views.historial),
    path("api/pedidos/<int:pid>/foto", views.subir_foto),
    path("api/pedidos/<int:pid>/<str:nombre>", views.accion),
    path("api/comprobantes/<str:archivo>", views.ver_comprobante),
    path("api/resumen", views.resumen),
    path("api/reportes", views.reportes),
]
