import os
import pymysql
from flask import Flask, render_template

app = Flask(__name__)

def obtener_conexion():
    # Cuando corre en Railway, usa las variables internas automáticamente
    return pymysql.connect(
        host=os.getenv("MYSQLHOST", "mysql.railway.internal"),
        port=int(os.getenv("MYSQLPORT", 3306)),
        user=os.getenv("MYSQLUSER", "root"),
        password=os.getenv("MYSQLPASSWORD", "clHhMVdjElOlchBapbLCJwxIgWSkLlXL"),
        database=os.getenv("MYSQLDATABASE", "railway"),
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route("/")
def index():
    productos = []
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT p.id_producto, p.modelo, p.precio, p.imagen_url, m.nombre AS marca
                FROM productos p
                JOIN marcas m ON p.id_marca = m.id_marca
            """)
            productos = cursor.fetchall()
        conexion.close()
    except Exception as e:
        print(f"Error DB: {e}")

    return render_template("index.html", productos=productos)

if __name__ == "__main__":
    puerto = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto)