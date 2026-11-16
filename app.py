import os
import pymysql
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import random
from datetime import datetime

app = Flask(__name__)
app.secret_key = "clave_secreta_prodevice_2026_segura"

# Asegurar persistencia de la cookie de sesión
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False  # Permite funcionar sobre HTTP sin certificado SSL local

# 1. Definir la función de conexión antes de usarla en las rutas
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
    {"id_producto": 1, "marca": "Apple", "modelo": "iPhone 17 Pro Max", "precio": 30999.00, "imagen_url": obtener_imagen_marca("Apple")},
    {"id_producto": 2, "marca": "Apple", "modelo": "iPhone 16", "precio": 19499.00, "imagen_url": obtener_imagen_marca("Apple")},
    {"id_producto": 3, "marca": "Samsung", "modelo": "Galaxy S26 Ultra", "precio": 27499.00, "imagen_url": obtener_imagen_marca("Samsung")},
    {"id_producto": 4, "marca": "Samsung", "modelo": "Galaxy A55", "precio": 8999.00, "imagen_url": obtener_imagen_marca("Samsung")},
    {"id_producto": 5, "marca": "Xiaomi", "modelo": "Xiaomi 15 Pro", "precio": 18999.00, "imagen_url": obtener_imagen_marca("Xiaomi")},
    {"id_producto": 6, "marca": "Motorola", "modelo": "Edge 50 Ultra", "precio": 14999.00, "imagen_url": obtener_imagen_marca("Motorola")}
]

def obtener_catalogo():
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT p.id_producto, p.modelo, p.precio, p.imagen_url, m.nombre AS marca
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
    return redirect(url_for("index"))

@app.route("/")
def index():
    marca_filtro = request.args.get("marca", "Todos")
    busqueda = request.args.get("q", "").strip()

    todos = obtener_catalogo()
    productos_filtrados = todos

    # 1. Filtro por marca
    if marca_filtro and marca_filtro.lower() != "todos":
        productos_filtrados = [p for p in productos_filtrados if p["marca"].lower() == marca_filtro.lower()]

    # 2. Filtro por buscador
    if busqueda:
        termino = busqueda.lower()
        productos_filtrados = [
            p for p in productos_filtrados
            if termino in p["modelo"].lower() or termino in p["marca"].lower()
        ]

    # Conteo de ítems en carrito para la burbuja roja/azul
    carrito = session.get("carrito", [])
    total_articulos = sum(item.get("cantidad", 1) for item in carrito)

    return render_template(
        "index.html",
        productos=productos_filtrados,
        marca_activa=marca_filtro,
        busqueda=busqueda,
        total_carrito=total_articulos
    )

@app.route("/agregar-al-carrito/<int:id_producto>")
def agregar_al_carrito(id_producto):
    if "carrito" not in session:
        session["carrito"] = []

    carrito = session["carrito"]
    todos = obtener_catalogo()
    producto = next((p for p in todos if p["id_producto"] == id_producto), None)

    if producto:
        # Verificar si ya estaba agregado para aumentar cantidad
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

    # Redirige a la misma página donde estaba el usuario
    return redirect(request.referrer or url_for("index"))

@app.route("/admin/agregar-producto", methods=["GET", "POST"])
def agregar_producto():
    # 1. Protección: Solo administradores pueden ingresar
    if not session.get("es_admin"):
        flash("Acceso restringido únicamente para administradores.")
        return redirect(url_for("login"))

    # Lista predeterminada de marcas para el selector
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

        try:
            precio = float(precio_raw)
        except ValueError:
            precio = 0.0

        # Asignar la imagen genérica si no se proporcionó una URL específica
        imagen_final = imagen_personalizada if imagen_personalizada else obtener_imagen_marca(marca_seleccionada)

        # 2. Intentar guardar en la Base de Datos si hay conexión
        guardado_en_bd = False
        try:
            conexion = obtener_conexion()
            with conexion.cursor() as cursor:
                # Buscar o insertar marca
                cursor.execute("SELECT id_marca FROM marcas WHERE LOWER(nombre) = %s", (marca_seleccionada.lower(),))
                marca_row = cursor.fetchone()
                if marca_row:
                    id_marca = marca_row["id_marca"]
                else:
                    cursor.execute("INSERT INTO marcas (nombre) VALUES (%s)", (marca_seleccionada,))
                    conexion.commit()
                    id_marca = cursor.lastrowid

                # Insertar producto
                cursor.execute("""
                    INSERT INTO productos (id_marca, modelo, precio, imagen_url)
                    VALUES (%s, %s, %s, %s)
                """, (id_marca, modelo, precio, imagen_final))
                conexion.commit()
                guardado_en_bd = True
            conexion.close()
            print(f"--> Producto '{modelo}' guardado exitosamente en BD.")
        except Exception as err:
            print(f"--> Base de datos no disponible ({err}). Guardando en catálogo local temporal.")

        # 3. Guardar también en la lista en memoria (garantiza que se vea al instante)
        nuevo_id = max([p["id_producto"] for p in PRODUCTOS_DEMO], default=0) + 1
        nuevo_producto = {
            "id_producto": nuevo_id,
            "marca": marca_seleccionada,
            "modelo": modelo,
            "precio": precio,
            "imagen_url": imagen_final
        }
        PRODUCTOS_DEMO.insert(0, nuevo_producto)  # Lo colocamos al inicio de la lista

        return redirect(url_for("index"))

    return render_template("agregar_producto.html", marcas=marcas_disponibles)

@app.route("/carrito")
def ver_carrito():
    carrito = session.get("carrito", [])
    subtotal = sum(item["precio"] * item["cantidad"] for item in carrito)
    total_articulos = sum(item["cantidad"] for item in carrito)
    return render_template("carrito.html", carrito=carrito, subtotal=subtotal, total_carrito=total_articulos)

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

    # 1. Obtener los datos actuales del producto
    producto = None
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT p.id_producto, p.modelo, p.precio, p.imagen_url, m.nombre AS marca
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

    # 2. Guardar modificaciones
    if request.method == "POST":
        nueva_marca = request.form.get("marca")
        nuevo_modelo = request.form.get("modelo", "").strip()
        precio_raw = request.form.get("precio", "0").strip()
        nueva_imagen = request.form.get("imagen_url", "").strip()

        try:
            nuevo_precio = float(precio_raw)
        except ValueError:
            nuevo_precio = float(producto["precio"])

        imagen_final = nueva_imagen if nueva_imagen else obtener_imagen_marca(nueva_marca)

        # Actualizar en BD si hay conexión
        try:
            conexion = obtener_conexion()
            with conexion.cursor() as cursor:
                # Obtener o crear id_marca
                cursor.execute("SELECT id_marca FROM marcas WHERE LOWER(nombre) = %s", (nueva_marca.lower(),))
                marca_row = cursor.fetchone()
                id_marca = marca_row["id_marca"] if marca_row else 1

                cursor.execute("""
                    UPDATE productos
                    SET id_marca = %s, modelo = %s, precio = %s, imagen_url = %s
                    WHERE id_producto = %s
                """, (id_marca, nuevo_modelo, nuevo_precio, imagen_final, id_producto))
                conexion.commit()
            conexion.close()
        except Exception as err:
            print(f"--> Aviso: Actualizando en memoria local ({err})")

        # Actualizar en memoria local demo
        for p in PRODUCTOS_DEMO:
            if p["id_producto"] == id_producto:
                p["marca"] = nueva_marca
                p["modelo"] = nuevo_modelo
                p["precio"] = nuevo_precio
                p["imagen_url"] = imagen_final
                break

        return redirect(url_for("index"))

    return render_template("editar_producto.html", producto=producto, marcas=marcas_disponibles)


@app.route("/admin/eliminar-producto/<int:id_producto>", methods=["POST"])
def eliminar_producto(id_producto):
    if not session.get("es_admin"):
        flash("Acceso restringido únicamente para administradores.")
        return redirect(url_for("login"))

    # Intentar eliminar de BD
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM productos WHERE id_producto = %s", (id_producto,))
            conexion.commit()
        conexion.close()
    except Exception as err:
        print(f"--> Aviso: Eliminando de memoria local ({err})")

    # Eliminar de la lista local en memoria
    global PRODUCTOS_DEMO
    PRODUCTOS_DEMO = [p for p in PRODUCTOS_DEMO if p["id_producto"] != id_producto]

    # Si estaba en el carrito de compras, removerlo
    if "carrito" in session:
        session["carrito"] = [item for item in session["carrito"] if item["id_producto"] != id_producto]
        session.modified = True

    return redirect(url_for("index"))

@app.route("/vaciar-carrito")
def vaciar_carrito():
    session.pop("carrito", None)
    return redirect(url_for("ver_carrito"))

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
        cp = request.form.get("cp", "").strip()
        metodo_pago = request.form.get("metodo_pago", "Tarjeta")

        direccion_completa = f"{direccion}, {ciudad} (CP {cp})"
        numero_orden = f"PD-{random.randint(100000, 999999)}"
        fecha_orden = datetime.now().strftime("%d/%m/%Y %H:%M")

        # Guardar orden y sus artículos en Aiven
        try:
            conexion = obtener_conexion()
            with conexion.cursor() as cursor:
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
            print(f"--> Orden {numero_orden} registrada en Aiven correctamente.")
        except Exception as err:
            print(f"--> Error guardando orden en Aiven: {err}")

        detalles_orden = {
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

        session["ultima_orden"] = detalles_orden
        session.pop("carrito", None)
        return redirect(url_for("confirmacion_pedido"))

    return render_template("checkout.html", carrito=carrito, subtotal=subtotal, envio=costo_envio, total=total)

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

@app.route("/confirmacion")
def confirmacion_pedido():
    orden = session.get("ultima_orden")
    if not orden:
        return redirect(url_for("index"))
    return render_template("confirmacion.html", orden=orden)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "").strip()

        print(f"--> Intento de login recibido: Correo='{correo}' | Password='{password}'")

        # 1. Comprobación directa sin tocar la BD remota:
        if correo == "admin123@gmail.com" and password == "admin123":
            session.permanent = True
            session["usuario_id"] = 1
            session["usuario_nombre"] = "Kevin Tapia Joachin"
            session["es_admin"] = True
            print("--> ¡Acceso concedido exitosamente como Administrador!")
            return redirect(url_for("index"))

        # 2. Si no coincide con las credenciales maestras, recién intenta la BD:
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
                    return redirect(url_for("index"))
        except Exception as err:
            print(f"--> Error consultando usuario en BD: {err}")

        flash("Credenciales incorrectas. Verifica tu correo o contraseña.")

    return render_template("login.html")

from werkzeug.security import generate_password_hash, check_password_hash

# --- REGISTRO PÚBLICO PARA CLIENTES ---
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

            # Iniciar sesión automáticamente al registrarse
            session.permanent = True
            session["usuario_id"] = nuevo_id
            session["usuario_nombre"] = nombre
            session["es_admin"] = False
            return redirect(url_for("index"))

        except Exception as err:
            print(f"--> Error registrando cliente en Aiven: {err}")
            flash("No se pudo completar el registro. Intenta de nuevo.")

    return render_template("registro.html")


# --- REGISTRO PRIVADO DE NUEVO ADMINISTRADOR ---
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
            flash(f"Administrador {nombre} creado exitosamente.")
            return redirect(url_for("index"))
        except Exception as err:
            print(f"--> Error creando admin en Aiven: {err}")
            flash("Error al guardar el administrador.")

    return render_template("nuevo_admin.html")

if __name__ == "__main__":
    puerto = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto)