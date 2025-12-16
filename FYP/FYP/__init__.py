import pymysql # type: ignore

pymysql.install_as_MySQLdb()
pymysql.version_info = (2, 2, 1, "final", 0)
