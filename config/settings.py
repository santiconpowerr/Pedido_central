import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Seguro por defecto: si se olvida la variable en produccion, DEBUG queda apagado.
# En desarrollo local pon DJANGO_DEBUG=true en tu .env.
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or ("clave-solo-para-desarrollo" if DEBUG else "")
if not SECRET_KEY:
    raise RuntimeError("Define DJANGO_SECRET_KEY en .env (obligatoria con DJANGO_DEBUG=false).")


def lista(nombre, defecto=""):
    return [x.strip() for x in os.environ.get(nombre, defecto).split(",") if x.strip()]


ALLOWED_HOSTS = lista("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = lista("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "pedidos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": []},
}]

# La hora de Colombia en la sesion de MySQL: NOW()/CURDATE() de los reportes y "ventas de hoy"
# no deben depender de la zona horaria del servidor (en la nube suele ser UTC).
_db_options = {"charset": "utf8mb4",
               "init_command": "SET time_zone='%s'" % os.environ.get("DB_TIME_ZONE", "-05:00")}
if os.environ.get("DB_SSL_CA"):
    _db_options["ssl"] = {"ca": os.environ["DB_SSL_CA"]}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "pedidocentral"),
        "USER": os.environ.get("DB_USER", "root"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "OPTIONS": _db_options,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Bogota"
USE_TZ = False  # las columnas DATETIME del SQL no llevan zona horaria

# Sesión en una cookie firmada: no necesita tablas extra ni "migrate".
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_AGE = 12 * 3600
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

X_FRAME_OPTIONS = "DENY"  # la app no debe poder incrustarse en un iframe ajeno

if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "true").lower() == "true"
    SECURE_REDIRECT_EXEMPT = [r"^api/salud$"]  # el health check de la plataforma puede ir por http
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "3600"))  # sube a 31536000 cuando todo funcione

# Cache en archivos: la comparten todos los workers de gunicorn (la de memoria es una por proceso).
CACHES = {"default": {
    "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
    "LOCATION": os.environ.get("CACHE_DIR", str(BASE_DIR / ".django_cache")),
}}

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
