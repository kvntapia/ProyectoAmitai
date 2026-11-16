import os
import pymysql
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import random
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_secreta_prodevice_2026_segura")

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False


def obtener_conexion():
    return pymysql.connect(
        host=os.getenv("MYSQLHOST"),
        port=int(os.getenv("MYSQLPORT", 3306)),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE"),
        cursorclass=pymysql.cursors.DictCursor,
        ssl={"ssl": {}},
        connect_timeout=5
    )


IMAGENES_MARCAS = {
    "apple": "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=600&auto=format&fit=crop&q=80",
    "samsung": "https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?w=600&auto=format&fit=crop&q=80",
    "xiaomi": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=600&auto=format&fit=crop&q=80",
    "motorola": "https://images.unsplash.com/photo-1567581935884-3349723552ca?w=600&auto=format&fit=crop&q=80",
    "default": "https://images.unsplash.com/photo-1511707171634-5f897ff02560?w=600&auto=format&fit=crop&q=80"
}


def obtener_imagen_marca(nombre_marca):
    if not nombre_marca:
        return IMAGENES_MARCAS["default"]
    return IMAGENES_MARCAS.get(nombre_marca.strip().lower(), IMAGENES_MARCAS["default"])


PRODUCTOS_DEMO = [
    {"id_producto": 1, "marca": "Apple", "modelo": "iPhone 17 Pro Max", "precio": 30999.00, "descripcion": "Pantalla Super Retina XDR de 6.9 pulgadas, chip A19 Pro, sistema de cámaras Pro de 48 MP y titanio de grado aeroespacial.", "imagen_url": obtener_imagen_marca("Apple")},
    {"id_producto": 2, "marca": "Apple", "modelo": "iPhone 16", "precio": 19499.00, "descripcion": "Pantalla OLED de 6.1 pulgadas, chip A18, Control de Cámara dedicado y batería de larga duración.", "imagen_url": obtener_imagen_marca("Apple")},
    {"id_producto": 3, "marca": "Samsung", "modelo": "Galaxy S26 Ultra", "precio": 27499.00, "descripcion": "Pantalla Dynamic AMOLED 2X QHD+ de 6.8 pulgadas, S Pen integrado, cámara principal de 200 MP y Galaxy AI.", "imagen_url": obtener_imagen_marca("Samsung")},
    {"id_producto": 4, "marca": "Samsung", "modelo": "Galaxy A55", "precio": 8999.00, "descripcion": "Pantalla Super AMOLED FHD+ de 6.6 pulgadas a 120 Hz, resistencia al agua IP67 y batería de 5,000 mAh.", "imagen_url": obtener_imagen_marca("Samsung")},
    {"id_producto": 5, "marca": "Xiaomi", "modelo": "Xiaomi 15 Pro", "precio": 18999.00, "descripcion": "Óptica profesional Leica Summilux, procesador Snapdragon de última generación y carga rápida HyperCharge de 120W.", "imagen_url": obtener_imagen_marca("Xiaomi")},
    {"id_producto": 6, "marca": "Motorola", "modelo": "Edge 50 Ultra", "precio": 14999.00, "descripcion": "Pantalla pOLED curva de 144 Hz, cámara teleobjetivo con zoom óptico 3x y carga TurboPower de 125W.", "imagen_url": obtener_imagen_marca("Motorola")}
]


def asegurar_columna_descripcion(cursor):
    try:
        cursor.execute("ALTER TABLE productos ADD COLUMN descripcion TEXT")
    except Exception:
        pass


def obtener_catalogo():
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            asegurar_columna_descripcion(cursor)
            cursor.execute("""
                SELECT p.id_producto, p.modelo, p.precio, p.imagen_url, p.descripcion, m.nombre AS marca
                FROM productos p
                JOIN marcas m ON p.id_marca = m.id_marca
                ORDER BY p.id_producto DESC
            """)
            productos = cursor.fetchall()
            for p in productos:
                if not p.get("imagen_url"):
                    p["imagen_url"] = obtener_imagen_marca(p.get("marca"))
        conexion.close()
        return productos
    except Exception as err:
        print(f"--> Error leyendo catálogo desde Aiven: {err}")
        return PRODUCTOS_DEMO


@app.route("/logout")
def logout():
    session.clear()
    flash("Has cerrado sesión correctamente.")
    return redirect(url_for("index"))


@app.route("/")
def index():
    marca_filtro = request.args.get("marca", "Todos")
    busqueda = request.args.get("q", "").strip()

    todos = obtener_catalogo()
    productos_filtrados = todos

    if marca_filtro and marca_filtro.lower() != "todos":
        productos_filtrados = [p for p in productos_filtrados if p["marca"].lower() == marca_filtro.lower()]

    if busqueda:
        termino = busqueda.lower()
        productos_filtrados = [
            p for p in productos_filtrados
            if termino in p["modelo"].lower() or termino in p["marca"].lower()
        ]

    carrito = session.get("carrito", [])
    total_articulos = sum(item.get("cantidad", 1) for item in carrito)

    return render_template(
        "index.html",
        productos=productos_filtrados,
        marca_activa=marca_filtro,
        busqueda=busqueda,
        total_carrito=total_articulos
    )


@app.route("/producto/<int:id_producto>")
def detalle_producto(id_producto):
    todos = obtener_catalogo()
    producto = next((p for p in todos if p["id_producto"] == id_producto), None)
    if not producto:
        flash("El dispositivo solicitado no fue encontrado.")
        return redirect(url_for("index"))

    carrito = session.get("carrito", [])
    total_articulos = sum(item.get("cantidad", 1) for item in carrito)
    return render_template("detalle_producto.html", producto=producto, total_carrito=total_articulos)


@app.route("/agregar-al-carrito/<int:id_producto>")
def agregar_al_carrito(id_producto):
    if "carrito" not in session:
        session["carrito"] = []

    carrito = session["carrito"]
    todos = obtener_catalogo()
    producto = next((p for p in todos if p["id_producto"] == id_producto), None)

    if producto:
        item_existente = next((item for item in carrito if item["id_producto"] == id_producto), None)
        if item_existente:
            item_existente["cantidad"] += 1
        else:
            carrito.append({
                "id_producto": producto["id_producto"],
                "modelo": producto["modelo"],
                "marca": producto["marca"],
                "precio": float(producto["precio"]),
                "imagen_url": producto["imagen_url"],
                "cantidad": 1
            })
        session.modified = True
        flash(f"'{producto['modelo']}' se agregó a tu carrito.")

    return redirect(request.referrer or url_for("index"))


@app.route("/carrito")
def ver_carrito():
    carrito = session.get("carrito", [])
    subtotal = sum(item["precio"] * item["cantidad"] for item in carrito)
    total_articulos = sum(item["cantidad"] for item in carrito)
    return render_template("carrito.html", carrito=carrito, subtotal=subtotal, total_carrito=total_articulos)


@app.route("/actualizar-carrito/<int:id_producto>/<accion>")
def actualizar_carrito(id_producto, accion):
    carrito = session.get("carrito", [])
    for item in carrito:
        if item["id_producto"] == id_producto:
            if accion == "sumar":
                item["cantidad"] += 1
            elif accion == "restar":
                item["cantidad"] -= 1
            break

    if accion == "eliminar":
        carrito = [item for item in carrito if item["id_producto"] != id_producto]
    else:
        carrito = [item for item in carrito if item["cantidad"] > 0]

    session["carrito"] = carrito
    session.modified = True
    return redirect(url_for("ver_carrito"))


@app.route("/vaciar-carrito")
def vaciar_carrito():
    session.pop("carrito", None)
    return redirect(url_for("ver_carrito"))


@app.route("/admin/agregar-producto", methods=["GET", "POST"])
def agregar_producto():
    if not session.get("es_admin"):
        flash("Acceso restringido únicamente para administradores.")
        return redirect(url_for("login"))

    marcas_disponibles = [
        {"id_marca": 1, "nombre": "Apple"},
        {"id_marca": 2, "nombre": "Samsung"},
        {"id_marca": 3, "nombre": "Xiaomi"},
        {"id_marca": 4, "nombre": "Motorola"}
    ]

    if request.method == "POST":
        marca_seleccionada = request.form.get("marca")
        modelo = request.form.get("modelo", "").strip()
        precio_raw = request.form.get("precio", "0").strip()
        imagen_personalizada = request.form.get("imagen_url", "").strip()
        descripcion = request.form.get("descripcion", "").strip()

        try:
            precio = float(precio_raw)
        except ValueError:
            precio = 0.0

        imagen_final = imagen_personalizada if imagen_personalizada else obtener_imagen_marca(marca_seleccionada)

        try:
            conexion = obtener_conexion()
            with conexion.cursor() as cursor:
                asegurar_columna_descripcion(cursor)
                cursor.execute("SELECT id_marca FROM marcas WHERE LOWER(nombre) = %s", (marca_seleccionada.lower(),))
                marca_row = cursor.fetchone()
                if marca_row:
                    id_marca = marca_row["id_marca"]
                else:
                    cursor.execute("INSERT INTO marcas (nombre) VALUES (%s)", (marca_seleccionada,))
                    conexion.commit()
                    id_marca = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO productos (id_marca, modelo, precio, imagen_url, descripcion)
                    VALUES (%s, %s, %s, %s, %s)
                """, (id_marca, modelo, precio, imagen_final, descripcion))
                conexion.commit()
            conexion.close()
        except Exception as err:
            print(f"--> Error guardando producto en BD: {err}")

        nuevo_id = max([p["id_producto"] for p in PRODUCTOS_DEMO], default=0) + 1
        PRODUCTOS_DEMO.insert(0, {
            "id_producto": nuevo_id,
            "marca": marca_seleccionada,
            "modelo": modelo,
            "precio": precio,
            "descripcion": descripcion,
            "imagen_url": imagen_final
        })
        flash(f"Dispositivo '{modelo}' publicado correctamente.")
        return redirect(url_for("index"))

    return render_template("agregar_producto.html", marcas=marcas_disponibles)


@app.route("/admin/editar-producto/<int:id_producto>", methods=["GET", "POST"])
def editar_producto(id_producto):
    if not session.get("es_admin"):
        flash("Acceso restringido únicamente para administradores.")
        return redirect(url_for("login"))

    marcas_disponibles = [
        {"id_marca": 1, "nombre": "Apple"},
        {"id_marca": 2, "nombre": "Samsung"},
        {"id_marca": 3, "nombre": "Xiaomi"},
        {"id_marca": 4, "nombre": "Motorola"}
    ]

    producto = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            asegurar_columna_descripcion(cursor)
            cursor.execute("""
                SELECT p.id_producto, p.modelo, p.precio, p.imagen_url, p.descripcion, m.nombre AS marca
                FROM productos p
                JOIN marcas m ON p.id_marca = m.id_marca
                WHERE p.id_producto = %s
            """, (id_producto,))
            producto = cursor.fetchone()
        conexion.close()
    except Exception:
        producto = next((p for p in PRODUCTOS_DEMO if p["id_producto"] == id_producto), None)

    if not producto:
        flash("El producto no existe.")
        return redirect(url_for("index"))

    if request.method == "POST":
        nueva_marca = request.form.get("marca")
        nuevo_modelo = request.form.get("modelo", "").strip()
        precio_raw = request.form.get("precio", "0").strip()
        nueva_imagen = request.form.get("imagen_url", "").strip()
        nueva_descripcion = request.form.get("descripcion", "").strip()

        try:
            nuevo_precio = float(precio_raw)
        except ValueError:
            nuevo_precio = float(producto["precio"])

        imagen_final = nueva_imagen if nueva_imagen else obtener_imagen_marca(nueva_marca)

        try:
            conexion = obtener_conexion()
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id_marca FROM marcas WHERE LOWER(nombre) = %s", (nueva_marca.lower(),))
                marca_row = cursor.fetchone()
                id_marca = marca_row["id_marca"] if marca_row else 1

                cursor.execute("""
                    UPDATE productos
                    SET id_marca = %s, modelo = %s, precio = %s, imagen_url = %s, descripcion = %s
                    WHERE id_producto = %s
                """, (id_marca, nuevo_modelo, nuevo_precio, imagen_final, nueva_descripcion, id_producto))
                conexion.commit()
            conexion.close()
        except Exception as err:
            print(f"--> Error actualizando producto en BD: {err}")

        for p in PRODUCTOS_DEMO:
            if p["id_producto"] == id_producto:
                p["marca"] = nueva_marca
                p["modelo"] = nuevo_modelo
                p["precio"] = nuevo_precio
                p["imagen_url"] = imagen_final
                p["descripcion"] = nueva_descripcion
                break

        flash(f"Cambios guardados en '{nuevo_modelo}'.")
        return redirect(url_for("index"))

    return render_template("editar_producto.html", producto=producto, marcas=marcas_disponibles)


@app.route("/admin/eliminar-producto/<int:id_producto>", methods=["POST"])
def eliminar_producto(id_producto):
    if not session.get("es_admin"):
        flash("Acceso restringido únicamente para administradores.")
        return redirect(url_for("login"))

    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM productos WHERE id_producto = %s", (id_producto,))
            conexion.commit()
        conexion.close()
    except Exception as err:
        print(f"--> Error eliminando de BD: {err}")

    global PRODUCTOS_DEMO
    PRODUCTOS_DEMO = [p for p in PRODUCTOS_DEMO if p["id_producto"] != id_producto]

    if "carrito" in session:
        session["carrito"] = [item for item in session["carrito"] if item["id_producto"] != id_producto]
        session.modified = True

    flash("Dispositivo eliminado del catálogo.")
    return redirect(url_for("index"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    carrito = session.get("carrito", [])
    if not carrito:
        flash("Tu carrito está vacío. Agrega productos antes de pagar.")
        return redirect(url_for("index"))

    subtotal = sum(item["precio"] * item["cantidad"] for item in carrito)
    costo_envio = 0.00 if subtotal >= 5000 else 199.00
    total = subtotal + costo_envio

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        email = request.form.get("email", "").strip()
        direccion = request.form.get("direccion", "").strip()
        ciudad = request.form.get("ciudad", "").strip()
        estado = request.form.get("estado", "").strip()
        cp = request.form.get("cp", "").strip()
        metodo_pago = request.form.get("metodo_pago", "Tarjeta")

        direccion_completa = f"{direccion}, {ciudad}, {estado} (CP {cp})"
        numero_orden = f"PD-{random.randint(100000, 999999)}"
        fecha_orden = datetime.now().strftime("%d/%m/%Y %H:%M")

        try:
            conexion = obtener_conexion()
            with conexion.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ordenes (
                        id_orden INT AUTO_INCREMENT PRIMARY KEY,
                        folio VARCHAR(20) NOT NULL UNIQUE,
                        cliente_nombre VARCHAR(150) NOT NULL,
                        cliente_email VARCHAR(150) NOT NULL,
                        direccion_envio VARCHAR(300) NOT NULL,
                        metodo_pago VARCHAR(50) NOT NULL,
                        subtotal DECIMAL(10, 2) NOT NULL,
                        costo_envio DECIMAL(10, 2) NOT NULL,
                        total DECIMAL(10, 2) NOT NULL,
                        fecha_orden DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS detalle_orden (
                        id_detalle INT AUTO_INCREMENT PRIMARY KEY,
                        id_orden INT NOT NULL,
                        id_producto INT,
                        modelo_producto VARCHAR(120) NOT NULL,
                        cantidad INT NOT NULL,
                        precio_unitario DECIMAL(10, 2) NOT NULL,
                        FOREIGN KEY (id_orden) REFERENCES ordenes(id_orden) ON DELETE CASCADE
                    )
                """)
                cursor.execute("""
                    INSERT INTO ordenes (folio, cliente_nombre, cliente_email, direccion_envio, metodo_pago, subtotal, costo_envio, total)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (numero_orden, nombre, email, direccion_completa, metodo_pago, subtotal, costo_envio, total))
                id_orden_creada = cursor.lastrowid

                for item in carrito:
                    cursor.execute("""
                        INSERT INTO detalle_orden (id_orden, id_producto, modelo_producto, cantidad, precio_unitario)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (id_orden_creada, item["id_producto"], item["modelo"], item["cantidad"], item["precio"]))

            conexion.commit()
            conexion.close()
        except Exception as err:
            print(f"--> Error guardando orden en Aiven: {err}")

        session["ultima_orden"] = {
            "folio": numero_orden,
            "cliente": nombre,
            "email": email,
            "direccion": direccion_completa,
            "metodo_pago": metodo_pago,
            "articulos": list(carrito),
            "subtotal": subtotal,
            "envio": costo_envio,
            "total": total,
            "fecha": fecha_orden
        }
        session.pop("carrito", None)
        return redirect(url_for("confirmacion_pedido"))

    return render_template("checkout.html", carrito=carrito, subtotal=subtotal, envio=costo_envio, total=total)


@app.route("/confirmacion")
def confirmacion_pedido():
    orden = session.get("ultima_orden")
    if not orden:
        return redirect(url_for("index"))
    return render_template("confirmacion.html", orden=orden)


@app.route("/admin/ordenes")
def ver_ordenes():
    if not session.get("es_admin"):
        flash("Acceso restringido únicamente para administradores.")
        return redirect(url_for("login"))

    ordenes = []
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM ordenes ORDER BY fecha_orden DESC")
            ordenes = cursor.fetchall()
            for o in ordenes:
                cursor.execute("SELECT * FROM detalle_orden WHERE id_orden = %s", (o["id_orden"],))
                o["detalles"] = cursor.fetchall()
        conexion.close()
    except Exception as err:
        print(f"--> Error consultando órdenes en Aiven: {err}")

    return render_template("ordenes_admin.html", ordenes=ordenes)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "").strip()

        if correo == "admin123@gmail.com" and password == "admin123":
            session.permanent = True
            session["usuario_id"] = 1
            session["usuario_nombre"] = "Kevin Tapia Joachin"
            session["es_admin"] = True
            flash("Bienvenido, Administrador.")
            return redirect(url_for("index"))

        try:
            conexion = obtener_conexion()
            with conexion.cursor() as cursor:
                cursor.execute("SELECT * FROM usuarios WHERE LOWER(email) = %s", (correo,))
                usuario = cursor.fetchone()
            conexion.close()

            if usuario:
                clave_db = usuario.get("password_hash") or usuario.get("password")
                clave_valida = (
                    clave_db == password or
                    (clave_db and clave_db.startswith(("scrypt:", "pbkdf2:")) and check_password_hash(clave_db, password))
                )
                if clave_valida:
                    session.permanent = True
                    session["usuario_id"] = usuario.get("id_usuario")
                    session["usuario_nombre"] = usuario.get("nombre")
                    session["es_admin"] = (usuario.get("rol") == "admin")
                    flash(f"Hola de nuevo, {usuario.get('nombre')}.")
                    return redirect(url_for("index"))
        except Exception as err:
            print(f"--> Error consultando usuario en BD: {err}")

        flash("Credenciales incorrectas. Verifica tu correo o contraseña.")

    return render_template("login.html")


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        apellido_p = request.form.get("apellido_paterno", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        password_segura = generate_password_hash(password)

        try:
            conexion = obtener_conexion()
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id_usuario FROM usuarios WHERE LOWER(email) = %s", (email,))
                if cursor.fetchone():
                    flash("Este correo ya está registrado. Intenta iniciar sesión.")
                    return redirect(url_for("registro"))

                cursor.execute("""
                    INSERT INTO usuarios (nombre, apellido_paterno, email, password_hash, rol)
                    VALUES (%s, %s, %s, %s, 'cliente')
                """, (nombre, apellido_p, email, password_segura))
                conexion.commit()
                nuevo_id = cursor.lastrowid
            conexion.close()

            session.permanent = True
            session["usuario_id"] = nuevo_id
            session["usuario_nombre"] = nombre
            session["es_admin"] = False
            flash("¡Cuenta creada con éxito! Bienvenido a ProDevice.")
            return redirect(url_for("index"))

        except Exception as err:
            print(f"--> Error registrando cliente en Aiven: {err}")
            flash("No se pudo completar el registro. Intenta de nuevo.")

    return render_template("registro.html")


@app.route("/admin/nuevo-admin", methods=["GET", "POST"])
def nuevo_admin():
    if not session.get("es_admin"):
        flash("Acceso restringido únicamente para administradores.")
        return redirect(url_for("login"))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        apellido_p = request.form.get("apellido_paterno", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        password_segura = generate_password_hash(password)

        try:
            conexion = obtener_conexion()
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id_usuario FROM usuarios WHERE LOWER(email) = %s", (email,))
                if cursor.fetchone():
                    flash("Ese correo ya existe en el sistema.")
                    return redirect(url_for("nuevo_admin"))

                cursor.execute("""
                    INSERT INTO usuarios (nombre, apellido_paterno, email, password_hash, rol)
                    VALUES (%s, %s, %s, %s, 'admin')
                """, (nombre, apellido_p, email, password_segura))
                conexion.commit()
            conexion.close()
            flash(f"Administrador {nombre} registrado exitosamente.")
            return redirect(url_for("index"))
        except Exception as err:
            print(f"--> Error creando admin en Aiven: {err}")
            flash("Error al guardar el administrador.")

    return render_template("nuevo_admin.html")


if __name__ == "__main__":
    puerto = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto)