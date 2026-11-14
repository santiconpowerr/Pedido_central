# Si no tienes mysqlclient instalado, usamos PyMySQL como driver (más fácil de instalar en Windows).
try:
    import MySQLdb  # noqa: F401
except ImportError:
    import pymysql

    pymysql.version_info = (2, 2, 1, "final", 0)  # Django exige >= 1.4.3
    pymysql.install_as_MySQLdb()
