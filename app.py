import os
import json
import base64
import sqlite3
from flask import Flask, request, make_response, redirect, url_for, render_template_string, jsonify

app = Flask(__name__)
DB_NAME = "universidad.db"
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
PUBLIC_LOGS_DIR = os.path.join(LOGS_DIR, "public")


# ==========================================
# 1. UTILIDADES JWT (Sin firma: alg="none")
# ==========================================
def b64url_encode(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def create_unsigned_jwt(sub: str, username: str, role: str) -> str:
    header = {"alg": "none", "typ": "JWT"}
    payload = {"sub": sub, "username": username, "role": role}
    # Formato identico al de la propuesta: header.payload.
    return f"{b64url_encode(header)}.{b64url_encode(payload)}."


def decode_unsigned_jwt(token: str):
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        # Agregar padding si hace falta para base64
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64 += "=" * padding
        payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
        return json.loads(payload_json)
    except Exception:
        return None


def get_current_user():
    token = request.cookies.get("SESSION_TOKEN")
    if not token:
        return None
    return decode_unsigned_jwt(token)


# ==========================================
# 2. INICIALIZACIÓN DE BD Y ARCHIVOS DE LOG
# ==========================================
def init_environment():
    # Crear directorios de logs para el Path Traversal
    os.makedirs(PUBLIC_LOGS_DIR, exist_ok=True)

    activity_log_content = (
        "[2026-10-15 09:00:12] INFO: Encuesta ID=3 abierta por admin.\n"
        "[2026-10-15 09:15:44] INFO: Nuevo voto registrado en survey_id=3.\n"
        "[2026-10-15 09:20:03] INFO: Nuevo voto registrado en survey_id=3.\n"
        "[2026-10-15 09:32:10] INFO: Comentario publicado por usuario 'fede' en survey_id=3.\n"
    )
    with open(os.path.join(PUBLIC_LOGS_DIR, "activity.log"), "w", encoding="utf-8") as f:
        f.write(activity_log_content)

    app_log_content = (
        "[2026-10-15 08:55:00] SYSTEM BOOT: Iniciando plataforma de encuestas universitarias v1.2\n"
        "[2026-10-15 08:55:01] DB_CONNECT: host=db.internal.frba.utn.edu.ar port=5432 user= encuesta_app pass=********\n"
        "[2026-10-15 08:55:02] DEBUG: Cargando rutas de administracion...\n"
        "[2026-10-15 08:55:02] WARN: Endpoint de auditoria de desarrollo sigue activo: GET /api/admin/votes?vote_id=xxxx\n"
        "[2026-10-15 08:55:03] INFO: Servidor escuchando en puerto 5000\n"
    )
    # Guardamos app.log tanto en /logs/ como en /logs/public/ para que funcione
    # tanto con ?file=app.log (como figura en el PDF) como con ?file=../app.log
    with open(os.path.join(LOGS_DIR, "app.log"), "w", encoding="utf-8") as f:
        f.write(app_log_content)
    with open(os.path.join(PUBLIC_LOGS_DIR, "app.log"), "w", encoding="utf-8") as f:
        f.write(app_log_content)

    # Crear Base de Datos SQLite
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE surveys (
            id INTEGER PRIMARY KEY,
            title TEXT
        )
    """)
    c.execute("""
        CREATE TABLE choices (
            id INTEGER PRIMARY KEY,
            survey_id INTEGER,
            label TEXT
        )
    """)
    c.execute("""
        CREATE TABLE votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vote_token TEXT,
            survey_id INTEGER,
            choice_id INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER,
            author TEXT,
            content TEXT
        )
    """)

    # Insertamos la encuesta ID = 3 tal como figura en el PDF
    c.execute("INSERT INTO surveys (id, title) VALUES (3, '¿Estás de acuerdo con el nuevo régimen de cursadas?')")
    c.execute("INSERT INTO choices (id, survey_id, label) VALUES (1, 3, 'Opción 1: Sí, estoy a favor')")
    c.execute("INSERT INTO choices (id, survey_id, label) VALUES (2, 3, 'Opción 2: No, estoy en contra')")

    # Cargamos 1 voto a favor (choice_id=1) y 5 votos en contra (choice_id=2)
    # Así al principio gana el "NO", y tras el SQLi los 6 votos pasan al "SÍ" (choice_id=1)
    initial_votes = [
        ("a8f3k29b1c", 3, 1),
        ("b7e2m91a4x", 3, 2),
        ("c9d1p48z2w", 3, 2),
        ("d4f8k12m9q", 3, 2),
        ("e2a6n73v5r", 3, 2),
        ("f5c3b89t1y", 3, 2),
    ]
    c.executemany("INSERT INTO votes (vote_token, survey_id, choice_id) VALUES (?, ?, ?)", initial_votes)

    c.execute(
        "INSERT INTO comments (survey_id, author, content) VALUES (3, 'luciana', 'Me parece que habría que revisar los horarios del turno noche.')"
    )
    c.execute(
        "INSERT INTO comments (survey_id, author, content) VALUES (3, 'tomas', 'Totalmente en contra de este cambio.')"
    )

    conn.commit()
    conn.close()


# ==========================================
# 3. PLANTILLA HTML RÚSTICA (Todo en uno)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Sistema de Encuestas Universitarias - UTN</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f4f4; margin: 20px; color: #222; }
        .container { max-width: 850px; margin: auto; background: #fff; padding: 20px; border: 2px solid #ccc; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }
        .badge { padding: 4px 8px; background: #ddd; font-weight: bold; border: 1px solid #999; }
        .badge-admin { background: #ffcccc; border-color: #cc0000; color: #900; }
        .box { border: 1px solid #bbb; padding: 15px; margin-bottom: 20px; background: #fafafa; }
        .admin-box { border: 2px dashed #cc0000; background: #fff5f5; padding: 15px; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        table, th, td { border: 1px solid #999; padding: 8px; text-align: left; }
        th { background: #eee; }
        textarea { width: 98%; height: 60px; margin-top: 8px; font-family: monospace; }
        button, .btn { padding: 6px 12px; cursor: pointer; background: #333; color: #fff; border: none; text-decoration: none; display: inline-block; font-size: 14px; }
        button:hover, .btn:hover { background: #555; }
        .btn-reset { background: #777; font-size: 12px; }
        .comment { border-bottom: 1px solid #ddd; padding: 8px 0; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div>
            <h2 style="margin:0;">Portal de Encuestas Universitarias</h2>
            <small>TP Seguridad en Aplicaciones Web - Grupo 4</small>
        </div>
        <div>
            <a href="/reset" class="btn btn-reset" onclick="return confirm('¿Reiniciar base de datos y borrar comentarios?')">Reiniciar Demo</a>
        </div>
    </div>

    <!-- BARRA DE SESIÓN / LOGIN RÁPIDO -->
    <div class="box">
        {% if user %}
            <span>Sesión iniciada como: <b>{{ user.username }}</b></span> |
            <span>Rol: <span class="badge {% if user.role == 'admin' %}badge-admin{% endif %}">{{ user.role }}</span></span>
            <a href="/logout" class="btn" style="float:right;">Cerrar Sesión</a>
        {% else %}
            <b>Iniciar Sesión:</b>
            <form action="/login" method="POST" style="display:inline; margin-left: 10px;">
                <input type="text" name="username" placeholder="Usuario (fede o admin)" required>
                <input type="password" name="password" placeholder="Contraseña" required>
                <button type="submit">Ingresar</button>
            </form>
            <div style="margin-top:8px; font-size:12px; color:#555;">
                <i>Credenciales de prueba -> Alumno atacante: <b>fede / 1234</b> | Administrador víctima: <b>admin / admin123</b></i>
            </div>
        {% endif %}
    </div>

    {% if user %}
        <!-- PANEL EXCLUSIVO PARA ADMINISTRADOR (Visible tras Paso 2: Session Hijacking) -->
        {% if user.role == 'admin' %}
        <div class="admin-box">
            <h3 style="margin-top:0; color:#900;">Panel de Administrador de Facultad</h3>
            <p style="margin: 5px 0;">Herramientas de moderación y auditoría del sistema:</p>
            <!-- PASO 3: Path Traversal en parámetro file -->
            <a href="/admin/logs?file=activity.log" target="_blank" class="btn" style="background:#900;">
                Exportar logs de actividad de encuestas (activity.log)
            </a>
        </div>
        {% endif %}

        <!-- ENCUESTA ACTIVA (ID = 3) -->
        <div class="box">
            <h3 style="margin-top:0;">Encuesta Activa #{{ survey[0] }}: {{ survey[1] }}</h3>
            
            <h4>Resultados parciales en vivo:</h4>
            <table>
                <tr>
                    <th>ID Opción (choice_id)</th>
                    <th>Opción</th>
                    <th>Cantidad de Votos</th>
                </tr>
                {% for c in results %}
                <tr>
                    <td><b>{{ c[0] }}</b></td>
                    <td>{{ c[1] }}</td>
                    <td><b>{{ c[2] }} votos</b></td>
                </tr>
                {% endfor %}
            </table>

            <form action="/vote" method="POST" style="margin-top: 15px;">
                <b>Emitir voto:</b>
                <label><input type="radio" name="choice_id" value="1" required> Opción 1 (A favor)</label>
                <label style="margin-left:15px;"><input type="radio" name="choice_id" value="2"> Opción 2 (En contra)</label>
                <button type="submit" style="margin-left:15px;">Votar</button>
            </form>
        </div>

        <!-- SECCIÓN DE COMENTARIOS (Vulnerable a Paso 1: Stored XSS) -->
        <div class="box">
            <h3 style="margin-top:0;">Comentarios de la Encuesta</h3>
            {% for author, content in comments %}
                <div class="comment">
                    <b>{{ author }} dijo:</b>
                    <!-- VULNERABILIDAD A05 (Stored XSS): Se usa | safe y no se escapan etiquetas HTML -->
                    <div>{{ content | safe }}</div>
                </div>
            {% endfor %}

            <form action="/comment" method="POST" style="margin-top: 15px;">
                <b>Dejar un comentario:</b><br>
                <textarea name="content" placeholder="Escribí tu comentario aquí..." required></textarea><br>
                <button type="submit" style="margin-top:5px;">Publicar Comentario</button>
            </form>
        </div>
    {% else %}
        <p style="text-align:center; padding: 30px; color:#666;">
            Por favor, iniciá sesión con tus credenciales universitarias para ver las encuestas activas.
        </p>
    {% endif %}
</div>
</body>
</html>
"""


# ==========================================
# 4. RUTAS Y ENDPOINTS VULNERABLES
# ==========================================
@app.route("/")
def index():
    user = get_current_user()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT id, title FROM surveys WHERE id = 3")
    survey = c.fetchone()

    c.execute("""
        SELECT choices.id, choices.label, COUNT(votes.id)
        FROM choices
        LEFT JOIN votes ON choices.id = votes.choice_id AND votes.survey_id = 3
        WHERE choices.survey_id = 3
        GROUP BY choices.id, choices.label
    """)
    results = c.fetchall()

    c.execute("SELECT author, content FROM comments WHERE survey_id = 3 ORDER BY id ASC")
    comments = c.fetchall()
    conn.close()

    return render_template_string(HTML_TEMPLATE, user=user, survey=survey, results=results, comments=comments)


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if username == "fede" and password == "1234":
        token = create_unsigned_jwt(sub="9876543210", username="fede", role="alumno")
    elif username == "admin" and password == "admin123":
        # Genera exactamente el JWT de ejemplo que pusieron en la presentación
        token = create_unsigned_jwt(sub="1234567890", username="test", role="admin")
    else:
        return "Credenciales inválidas. <a href='/'>Volver</a>", 401

    resp = make_response(redirect(url_for("index")))
    # VULNERABILIDAD A02 / A07: Cookie sin flag HttpOnly (httponly=False)
    # Permite que JavaScript la lea mediante document.cookie
    resp.set_cookie("SESSION_TOKEN", token, httponly=False, path="/")
    return resp


@app.route("/logout")
def logout():
    resp = make_response(redirect(url_for("index")))
    resp.delete_cookie("SESSION_TOKEN", path="/")
    return resp


@app.route("/vote", methods=["POST"])
def vote():
    user = get_current_user()
    if not user:
        return "No autenticado", 401

    choice_id = request.form.get("choice_id")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO votes (vote_token, survey_id, choice_id) VALUES (?, 3, ?)",
        (os.urandom(5).hex(), choice_id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


# PASO 1: Endpoint que guarda el comentario sin sanitizar (Stored XSS)
@app.route("/comment", methods=["POST"])
def add_comment():
    user = get_current_user()
    if not user:
        return "No autenticado", 401

    content = request.form.get("content", "")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO comments (survey_id, author, content) VALUES (3, ?, ?)",
        (user.get("username"), content),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


# PASO 3: Endpoint vulnerable a Path Traversal (A02: Security Misconfiguration)
@app.route("/admin/logs")
def admin_logs():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return "403 Forbidden - Se requiere rol de Administrador de Facultad", 403

    filename = request.args.get("file", "activity.log")
    # VULNERABILIDAD: Concatenación directa sin validar ni sanitizar rutas (Path Traversal)
    filepath = os.path.join(PUBLIC_LOGS_DIR, filename)

    if not os.path.exists(filepath):
        return f"Archivo no encontrado: {filename}", 404

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    resp = make_response(content, 200)
    resp.mimetype = "text/plain"
    return resp


# PASO 4: Endpoint oculto vulnerable a SQL Injection con Stacked Queries (A01 + A05)
@app.route("/api/admin/votes")
def api_admin_votes():
    user = get_current_user()
    # Sin el Paso 2 (Session Hijacking), este chequeo devuelve 403 e impide el ataque
    if not user or user.get("role") != "admin":
        return jsonify({"error": "403 Forbidden - Acceso exclusivo para administradores"}), 403

    vote_id = request.args.get("vote_id", "1")

    # VULNERABILIDAD: Concatenación directa del parámetro en la consulta SQL
    raw_query = f"SELECT id, vote_token, survey_id, choice_id FROM votes WHERE id = {vote_id}"

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    try:
        # Eliminamos comentarios SQL (--) y separamos por ';' para permitir Stacked Queries
        clean_query = raw_query.split("--")[0]
        statements = [s.strip() for s in clean_query.split(";") if s.strip()]

        first_row = None
        for idx, stmt in enumerate(statements):
            c.execute(stmt)
            if idx == 0:
                first_row = c.fetchone()

        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({"sql_error": str(e), "executed_query": raw_query}), 500

    conn.close()

    if first_row:
        return jsonify({
            "vote_id": first_row[0],
            "vote_token": first_row[1],
            "survey_id": first_row[2],
            "choice_id": first_row[3]
        })
    else:
        # Si es 99999, devuelve vacío sin levantar sospechas pero habiendo ejecutado el UPDATE
        return jsonify({"message": "Sin resultados", "data": None}), 200


@app.route("/reset")
def reset():
    init_environment()
    resp = make_response(redirect(url_for("index")))
    resp.delete_cookie("SESSION_TOKEN", path="/")
    return resp


if __name__ == "__main__":
    init_environment()
    print("[*] Entorno inicializado. Corriendo en http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
