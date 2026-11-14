"""
Modelos que mapean las tablas de database/pedidocentral.sql.

managed = False: Django NO crea ni modifica estas tablas (las crea el .sql, con sus
triggers y procedimientos). En Pedido, Pago, Cliente y DetallePedido solo se declaran las
columnas que Django escribe; las demás (estado, total, fechas) las llena la base de datos.
"""
from django.db import models


class Rol(models.Model):
    id = models.AutoField(primary_key=True, db_column="idRol")
    nombre = models.CharField(max_length=30)
    descripcion = models.CharField(max_length=150, null=True)

    class Meta:
        managed = False
        db_table = "rol"


class Usuario(models.Model):
    id = models.AutoField(primary_key=True, db_column="idUsuario")
    rol = models.ForeignKey(Rol, on_delete=models.DO_NOTHING, db_column="idRol")
    nombre = models.CharField(max_length=100)
    username = models.CharField(max_length=40)
    password_hash = models.CharField(max_length=255, db_column="passwordHash")
    activo = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "usuario"


class Cliente(models.Model):
    id = models.AutoField(primary_key=True, db_column="idCliente")
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, unique=True)
    direccion = models.CharField(max_length=200)

    class Meta:
        managed = False
        db_table = "cliente"


class Pedido(models.Model):
    id = models.AutoField(primary_key=True, db_column="idPedido")
    cliente = models.ForeignKey(Cliente, on_delete=models.DO_NOTHING, db_column="idCliente")
    usuario_cajera = models.ForeignKey(Usuario, on_delete=models.DO_NOTHING, db_column="idUsuarioCajera")
    canal = models.CharField(max_length=30)
    direccion_entrega = models.CharField(max_length=200, db_column="direccionEntrega")
    observaciones = models.CharField(max_length=300, null=True)

    class Meta:
        managed = False
        db_table = "pedido"


class DetallePedido(models.Model):
    id = models.AutoField(primary_key=True, db_column="idDetalle")
    pedido = models.ForeignKey(Pedido, on_delete=models.DO_NOTHING, db_column="idPedido")
    producto = models.CharField(max_length=100)
    cantidad = models.PositiveSmallIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        managed = False
        db_table = "detalle_pedido"


class Pago(models.Model):
    id = models.AutoField(primary_key=True, db_column="idPago")
    pedido = models.OneToOneField(Pedido, on_delete=models.DO_NOTHING, db_column="idPedido")
    medio_pago = models.CharField(max_length=30, db_column="medioPago")
    url_comprobante = models.CharField(max_length=500, null=True, db_column="urlComprobante")
    validado = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "pago"
