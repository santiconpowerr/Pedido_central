from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from pedidos.models import Usuario


class Command(BaseCommand):
    help = "Asigna una clave a los usuarios que aún tienen 'CAMBIAR_POR_HASH' (admin, cajera, cocina, domi)."

    def add_arguments(self, parser):
        parser.add_argument("clave", help="Mínimo 8 caracteres")

    def handle(self, *args, **opts):
        if len(opts["clave"]) < 8:
            raise CommandError("La clave debe tener al menos 8 caracteres.")
        pendientes = Usuario.objects.filter(password_hash="CAMBIAR_POR_HASH")
        n = 0
        for u in pendientes:
            Usuario.objects.filter(pk=u.pk).update(password_hash=make_password(opts["clave"]))
            self.stdout.write("Clave asignada a: " + u.username)
            n += 1
        if not n:
            self.stdout.write("No hay usuarios pendientes de clave.")
