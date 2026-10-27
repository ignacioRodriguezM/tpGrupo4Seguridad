import os
import json
import base64
import sqlite3
import logging
from flask import Flask, request, make_response, redirect, url_for, render_template_string, jsonify

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "universidad.db")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
PUBLIC_LOGS_DIR = os.path.join(LOGS_DIR, "public")

# Identificador nuevo en cada arranque: invalida cookies de ejecuciones anteriores.
APP_RUN_ID = os.urandom(16).hex()


def configure_logging():
    """Configura logs persistentes; las consultas SQL se registran en DEBUG."""
    os.makedirs(PUBLIC_LOGS_DIR, exist_ok=True)
    # Flask no expone setLevel directamente; el nivel se configura en app.logger.
    app.logger.setLevel(logging.DEBUG)
    # Evita agregar handlers duplicados si se reinicializa la demo.
    if not getattr(app, "_file_logging_configured", False):
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        for log_path in (os.path.join(LOGS_DIR, "app.log"), os.path.join(PUBLIC_LOGS_DIR, "app.log")):
            handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(formatter)
            app.logger.addHandler(handler)
        app.logger.propagate = False
        app._file_logging_configured = True
    app.logger.info("Logger inicializado")

# ==========================================
# 1. UTILIDADES JWT (laboratorio: JWT sin firma)
# ==========================================
def b64url_encode(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def create_unsigned_jwt(sub: str, username: str, role: str) -> str:
    header = {"alg": "none", "typ": "JWT"}
    # APP_RUN_ID cambia cada vez que se inicia el proceso Flask.
    payload = {"sub": sub, "username": username, "role": role, "run_id": APP_RUN_ID}
    return f"{b64url_encode(header)}.{b64url_encode(payload)}."


def decode_unsigned_jwt(token: str):
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
        # Una cookie de una ejecución anterior ya no autentica al usuario.
        if payload.get("run_id") != APP_RUN_ID:
            return None
        return payload
    except Exception:
        return None


def get_current_user():
    token = request.cookies.get("SESSION_TOKEN")
    return decode_unsigned_jwt(token) if token else None


def db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.set_trace_callback(lambda sql: app.logger.debug("SQL: %s", sql))
    return conn


def log_activity(message):
    """Agrega al log visible para el admin solo una descripción funcional de la acción."""
    log_path = os.path.join(PUBLIC_LOGS_DIR, "activity.log")
    timestamp = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] INFO: {message}\n")


# ==========================================
# 2. INICIALIZACIÓN DE BD Y LOGS
# ==========================================
def init_environment():
    os.makedirs(PUBLIC_LOGS_DIR, exist_ok=True)


    # Limpiar logs ANTES de configurar el logger
    for path in (os.path.join(LOGS_DIR, "app.log"), os.path.join(PUBLIC_LOGS_DIR, "app.log")):
        with open(path, "w", encoding="utf-8") as f:
            f.write("")
    
    configure_logging()


    # Inicializar activity.log con fechas reales
    with open(os.path.join(PUBLIC_LOGS_DIR, "activity.log"), "w", encoding="utf-8") as f:
        f.write("")
    log_activity("Nuevo voto registrado en «¿Estás de acuerdo con el nuevo régimen de cursadas?». Votos por opción: A favor: 4; En contra: 3. Total de votos contabilizados: 7.")
    log_activity("Nuevo voto registrado en «¿Estás de acuerdo con el nuevo régimen de cursadas?». Votos por opción: A favor: 5; En contra: 3. Total de votos contabilizados: 8.")

    app.logger.info("SYSTEM BOOT: Iniciando plataforma de encuestas universitarias v1.2")
    app.logger.info("DB_CONNECT: host=db.internal.frba.utn.edu.ar port=5432 user=encuesta_app pass=********")
    app.logger.debug("Cargando rutas de administracion...")
    app.logger.warning("Endpoint de auditoria de desarrollo sigue activo: GET /api/admin/votes?vote_id=xxxx")
    app.logger.info("Servidor escuchando en puerto 5000")
            

    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    conn = sqlite3.connect(DB_NAME)
    conn.set_trace_callback(lambda sql: app.logger.debug("SQL: %s", sql))
    c = conn.cursor()
    c.execute("CREATE TABLE surveys (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL)")
    c.execute("CREATE TABLE choices (id INTEGER PRIMARY KEY AUTOINCREMENT, survey_id INTEGER NOT NULL, label TEXT NOT NULL)")
    c.execute("""CREATE TABLE votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vote_token TEXT,
        survey_id INTEGER NOT NULL,
        choice_id INTEGER NOT NULL,
        username TEXT
    )""")
    c.execute("""CREATE TABLE comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        survey_id INTEGER NOT NULL,
        author TEXT NOT NULL,
        content TEXT NOT NULL,
        UNIQUE(survey_id, author)
    )""")
    c.execute("INSERT INTO surveys (id, title) VALUES (3, '¿Estás de acuerdo con el nuevo régimen de cursadas?')")
    c.execute("INSERT INTO choices (id, survey_id, label) VALUES (1, 3, 'Opción 1: Sí, estoy a favor')")
    c.execute("INSERT INTO choices (id, survey_id, label) VALUES (2, 3, 'Opción 2: No, estoy en contra')")
    initial_votes = [
        # Votos anónimos de ejemplo para que los resultados tengan datos iniciales.
        ("a8f3k29b1c", 3, 1, None), ("b7e2m91a4x", 3, 2, None),
        ("c9d1p48z2w", 3, 2, None), ("d4f8k12m9q", 3, 2, None),
        ("e2a6n73v5r", 3, 2, None), ("f5c3b89t1y", 3, 2, None),
        # Luciana y Tomás ya respondieron la encuesta en el estado inicial de la demo.
        ("luciana-demo-vote", 3, 1, "luciana"),
        ("tomas-demo-vote", 3, 2, "tomas"),
    ]
    c.executemany("INSERT INTO votes (vote_token, survey_id, choice_id, username) VALUES (?, ?, ?, ?)", initial_votes)
    # Comentarios preexistentes para la demo; se muestran anónimamente en el panel admin.
    c.execute("INSERT INTO comments (survey_id, author, content) VALUES (3, 'luciana', 'Me parece que habría que revisar los horarios del turno noche.')")
    c.execute("INSERT INTO comments (survey_id, author, content) VALUES (3, 'tomas', 'Totalmente en contra de este cambio.')")
    conn.commit()
    conn.close()
    app.logger.info("Base de datos inicializada y datos de demo cargados")


# ==========================================
# 3. PLANTILLAS HTML (todo permanece en este archivo)
# ==========================================
BASE_STYLE = """
<style>
:root {
  --page: #f5f7fb; --surface: #fff; --ink: #182230; --muted: #667085;
  --line: #e5e9f0; --brand: #3457d5; --brand-dark: #2646bb; --brand-soft: #eef2ff;
  --success: #087e6e; --danger: #b42318; --shadow: 0 8px 28px rgba(16,24,40,.055);
}
* { box-sizing: border-box; }
html { min-height: 100%; }
body { margin: 0; background: var(--page); color: var(--ink); font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 15px; line-height: 1.55; }
a { color: var(--brand); text-decoration: none; }
a:hover { color: var(--brand-dark); }
.topbar { background: var(--surface); border-bottom: 1px solid var(--line); }
.topbar-inner { max-width: 1180px; min-height: 76px; padding: 0 28px; margin: auto; display: flex; align-items: center; justify-content: space-between; gap: 24px; }
.brand { display: flex; align-items: center; gap: 13px; color: var(--ink); min-width: 0; }
.brand-mark { display: grid; place-items: center; flex: 0 0 42px; width: 42px; height: 42px; border-radius: 12px; background: var(--brand); color: white; font-weight: 800; letter-spacing: -.04em; font-size: 13px; }
.brand-copy { min-width: 0; }
.brand-name { display: block; font-size: 16px; font-weight: 750; letter-spacing: -.025em; line-height: 1.25; }
.brand-caption { display: block; color: var(--muted); font-size: 12px; margin-top: 3px; }
.account-area { display: flex; align-items: center; gap: 14px; }
.account { display: flex; align-items: center; gap: 10px; }
.avatar { display: grid; place-items: center; width: 38px; height: 38px; flex: 0 0 38px; border-radius: 50%; background: #edf0f7; color: #475467; }
.avatar svg { width: 20px; height: 20px; }
.account-meta { line-height: 1.3; }
.account-name { display: block; font-size: 13px; font-weight: 700; }
.account-role { display: block; color: var(--muted); font-size: 12px; margin-top: 3px; }
.logout { display: inline-flex; align-items: center; gap: 7px; padding: 9px 12px; border: 1px solid var(--line); border-radius: 9px; color: #475467; font-size: 13px; font-weight: 650; background: white; }
.logout:hover { background: #f8fafc; color: var(--ink); }
.logout svg { width: 16px; height: 16px; }
.nav-wrap { background: #fff; border-bottom: 1px solid var(--line); }
.nav { max-width: 1180px; margin: auto; padding: 0 28px; display: flex; gap: 6px; min-height: 54px; align-items: stretch; }
.nav a { display: inline-flex; align-items: center; padding: 0 15px; border-bottom: 2px solid transparent; color: #596579; font-size: 13px; font-weight: 650; white-space: nowrap; }
.nav a:hover { color: var(--brand); background: #fafbff; }
.nav a.active { color: var(--brand); border-bottom-color: var(--brand); }
main { max-width: 1180px; padding: 34px 28px 56px; margin: auto; min-height: calc(100vh - 180px); }
.page-heading { margin: 0 0 24px; }
.eyebrow { margin: 0 0 6px; color: var(--brand); font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .09em; }
h1 { margin: 0; font-size: clamp(25px, 3vw, 32px); line-height: 1.2; letter-spacing: -.045em; font-weight: 760; }
.subtitle { margin: 9px 0 0; max-width: 720px; color: var(--muted); font-size: 14px; }
.box, .admin-box, .panel { padding: 24px; margin: 0 0 18px; background: var(--surface); border: 1px solid var(--line); border-radius: 13px; box-shadow: var(--shadow); }
.admin-box { border-top: 3px solid #8b91ee; }
.box > h3, .admin-box > h3, .panel > h3 { margin: 0 0 16px; font-size: 17px; letter-spacing: -.02em; }
h4 { margin: 24px 0 10px; font-size: 14px; font-weight: 750; }
p { margin-top: 8px; }
.muted { color: var(--muted); font-size: 13px; }
.badge { display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 6px; background: #f2f4f7; color: #475467; font-size: 11px; font-weight: 750; }
.badge-admin { background: #fff0f0; color: #a61b1b; }
.btn, button { display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 39px; padding: 9px 14px; border: 1px solid transparent; border-radius: 8px; background: var(--brand); color: white; font: inherit; font-size: 13px; font-weight: 700; line-height: 1.2; text-decoration: none; cursor: pointer; transition: background .15s, border-color .15s, transform .15s; }
.btn:hover, button:hover { background: var(--brand-dark); color: white; }
.btn-secondary { background: #fff; border-color: #d8deea; color: #344054; box-shadow: none; }
.btn-secondary:hover { background: #f8fafc; border-color: #c5cede; color: #182230; }
.btn-small { min-height: 34px; padding: 7px 11px; }
.back-link { display: inline-flex; align-items: center; gap: 7px; margin-bottom: 18px; font-size: 13px; font-weight: 700; }
.list { display: flex; flex-direction: column; }
.list-item { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 17px 0; border-bottom: 1px solid var(--line); }
.list-item:first-child { padding-top: 4px; }
.list-item:last-child { padding-bottom: 2px; border-bottom: 0; }
.item-title { font-size: 14px; font-weight: 650; color: #253044; }
.item-meta { display: block; margin-top: 4px; color: var(--muted); font-size: 12px; }
.empty-state { padding: 34px 18px; text-align: center; background: #fafbfe; border: 1px dashed #d8dfeb; border-radius: 10px; color: var(--muted); }
.empty-icon { margin: 0 auto 10px; width: 42px; height: 42px; border-radius: 50%; background: #edf2ff; color: var(--brand); display: grid; place-items: center; font-size: 19px; }
.stat-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-bottom: 20px; }
.stat-card { background: white; border: 1px solid var(--line); border-radius: 12px; padding: 20px; box-shadow: var(--shadow); }
.stat-label { color: var(--muted); font-size: 13px; }
.stat-value { display: block; font-size: 28px; font-weight: 780; letter-spacing: -.04em; margin-top: 4px; }
form { margin-top: 12px; }
input[type=text], input[type=password], input[type=number], textarea { width: 100%; max-width: 100%; padding: 11px 13px; margin: 6px 0 13px; border: 1px solid #d0d7e2; border-radius: 8px; background: white; color: var(--ink); font: inherit; outline: none; transition: border .15s, box-shadow .15s; }
input[type=text]:focus, input[type=password]:focus, input[type=number]:focus, textarea:focus { border-color: #8094f3; box-shadow: 0 0 0 3px rgba(52,87,213,.12); }
textarea { min-height: 112px; resize: vertical; }
input[type=radio] { width: 17px; height: 17px; accent-color: var(--brand); vertical-align: -3px; margin-right: 9px; }
.choice-row { display: block; margin: 9px 0; padding: 13px 14px; border: 1px solid var(--line); border-radius: 9px; cursor: pointer; }
.choice-row:hover { background: #fafbff; border-color: #c8d1f8; }
label { color: #344054; }
.field-label { display: block; font-size: 13px; font-weight: 700; margin-top: 14px; }
table { width: 100%; margin-top: 12px; border-collapse: separate; border-spacing: 0; overflow: hidden; border: 1px solid var(--line); border-radius: 10px; }
th, td { padding: 13px 15px; text-align: left; border-bottom: 1px solid var(--line); }
th { background: #f8f9fc; color: #596579; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }
tr:last-child td { border-bottom: 0; }
td { background: #fff; }
.comment-card { padding: 15px 16px; margin: 10px 0; border: 1px solid var(--line); border-radius: 9px; background: #fcfcfe; overflow-wrap: anywhere; }
.login-card { max-width: 510px; margin: 30px auto; }
.login-error { display:flex; gap:12px; align-items:flex-start; margin:18px 0 0; padding:13px 15px; border:1px solid #fecdca; border-radius:12px; background:#fff1f0; color:#912018; font-size:14px; }
.login-error-icon { display:grid; place-items:center; flex:0 0 24px; height:24px; border-radius:50%; background:#fee4e2; font-weight:800; }
.login-card form { margin-top: 22px; }
.login-card .btn { width: 100%; margin-top: 4px; }
.login-card input { margin-bottom: 10px; }
.footer { padding: 18px 28px; color: #8a94a6; font-size: 12px; border-top: 1px solid var(--line); background: white; }
.footer-inner { max-width: 1180px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.reset-demo { background: #fff; border-color: #fecdca; color: #b42318; white-space: nowrap; }
.reset-demo:hover { background: #fff1f0; border-color: #fda29b; color: #912018; }
@media (max-width: 720px) {
  .topbar-inner { padding: 14px 16px; min-height: 68px; gap: 12px; }
  .footer-inner { align-items: flex-start; flex-direction: column; }
  .brand-caption { display: none; }
  .brand-mark { width: 38px; height: 38px; flex-basis: 38px; }
  .brand-name { font-size: 14px; }
  .account { gap: 7px; }
  .account-meta { display: none; }
  .logout { padding: 9px; font-size: 0; gap: 0; }
  .nav { padding: 0 12px; overflow-x: auto; }
  .nav a { padding: 0 12px; font-size: 12px; }
  main { padding: 25px 16px 40px; }
  .box, .admin-box, .panel { padding: 18px; }
  .list-item { align-items: flex-start; }
  .list-item .btn { flex-shrink: 0; }
  .stat-grid { grid-template-columns: 1fr; }
}
@media (max-width: 440px) {
  .topbar-inner { align-items: flex-start; }
  .brand-name { max-width: 150px; }
  .avatar { display: none; }
  .list-item { flex-direction: column; gap: 10px; }
  .list-item .btn { align-self: flex-start; }
  th, td { padding: 10px 9px; }
}
</style>
"""

HTML_TEMPLATE = """<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>Portal de Encuestas Universitarias</title>""" + BASE_STYLE + """</head><body>
<header class="topbar"><div class="topbar-inner">
  <a class="brand" href="/" aria-label="Portal de Encuestas Universitarias - Inicio"><span class="brand-mark">PU</span><span class="brand-copy"><span class="brand-name">Portal Universitario</span><span class="brand-caption">Sistema de encuestas académicas</span></span></a>
  {% if user %}<div class="account-area"><div class="account"><span class="avatar" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="3.5"/><path d="M4.8 20c.7-3.5 3.2-5.3 7.2-5.3s6.5 1.8 7.2 5.3" stroke-linecap="round"/></svg></span><span class="account-meta"><span class="account-name">{{ user.username }}</span><span class="account-role">{% if user.role == 'admin' %}Administrador{% else %}Usuario{% endif %}</span></span></div><a href="/logout" class="logout"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M10 17l5-5-5-5M15 12H3" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6" stroke-linecap="round"/></svg>Cerrar sesión</a></div>
  {% else %}<span class="muted">Acceso al portal</span>{% endif %}
</div></header>
{% if user %}<div class="nav-wrap"><nav class="nav" aria-label="Navegación principal">
{% if user.role == 'admin' %}
<a href="/" class="{% if view == 'home' %}active{% endif %}">Inicio</a><a href="/?view=create" class="{% if view == 'create' %}active{% endif %}">Crear encuesta</a><a href="/?view=admin_surveys" class="{% if view == 'admin_surveys' %}active{% endif %}">Encuestas respondidas</a><a href="/?view=logs" class="{% if view == 'logs' %}active{% endif %}">Actividad</a>
{% else %}
<a href="/" class="{% if view == 'home' %}active{% endif %}">Inicio</a><a href="/?view=pending" class="{% if view == 'pending' %}active{% endif %}">Encuestas pendientes{% if pending %} <span style="margin-left:6px;opacity:.7">{{ pending|length }}</span>{% endif %}</a><a href="/?view=answered" class="{% if view == 'answered' %}active{% endif %}">Encuestas respondidas</a>
{% endif %}
</nav></div>{% endif %}
<main>
{% if not user %}
<section class="box login-card"><p class="eyebrow">Bienvenido/a</p><h1>Ingresá al portal</h1><p class="subtitle">Accedé para responder encuestas académicas o administrar sus resultados.</p>{% if login_error %}<div class="login-error" role="alert"><span class="login-error-icon">!</span><div><strong>No pudimos iniciar tu sesión</strong><br>El usuario o la contraseña son incorrectos. Revisá los datos e intentá nuevamente.</div></div>{% endif %}<form action="/login" method="POST"><label class="field-label" for="username">Usuario</label><input id="username" name="username" type="text" placeholder="Ingresá tu usuario" autocomplete="username" required><label class="field-label" for="password">Contraseña</label><input id="password" name="password" type="password" placeholder="Ingresá tu contraseña" autocomplete="current-password" required><button type="submit" class="btn">Iniciar sesión</button></form>
{% elif user.role == 'admin' %}
{% if view == 'home' %}<div class="page-heading"><p class="eyebrow">Administración</p><h1>Panel de administración</h1><p class="subtitle">Gestioná las encuestas, consultá los resultados y revisá la actividad del sistema.</p></div><div class="stat-grid"><a class="stat-card" href="/?view=create"><span class="stat-label">Gestión</span><span class="stat-value" style="font-size:20px">Crear encuesta</span><span class="muted">Publicá una nueva pregunta y sus opciones →</span></a><a class="stat-card" href="/?view=admin_surveys"><span class="stat-label">Resultados</span><span class="stat-value" style="font-size:20px">Ver encuestas</span><span class="muted">Consultá votos y comentarios →</span></a></div><section class="panel"><h3>Actividad del sistema</h3><p class="muted">Los registros de actividad están disponibles desde la sección Actividad de la barra de navegación.</p><a href="/?view=logs" class="btn btn-secondary">Consultar actividad</a></section>
{% elif view == 'create' %}<div class="page-heading"><p class="eyebrow">Administración / Encuestas</p><h1>Crear encuesta</h1><p class="subtitle">Definí la pregunta y agregá las opciones de respuesta.</p></div><section class="panel"><form action="/admin/surveys/create" method="POST"><label class="field-label" for="title">Pregunta de la encuesta</label><input id="title" type="text" name="title" placeholder="Ej.: ¿Qué te pareció la cursada?" required><label class="field-label" for="choices">Opciones de respuesta</label><textarea id="choices" name="choices" placeholder="Una opción por línea&#10;Otra opción" required></textarea><p class="muted">Ingresá al menos dos opciones, una por línea.</p><button type="submit" class="btn">Crear encuesta</button></form></section>
{% elif view == 'admin_surveys' %}<div class="page-heading"><p class="eyebrow">Administración / Resultados</p><h1>{% if selected %}Resultados de la encuesta{% else %}Encuestas respondidas{% endif %}</h1><p class="subtitle">Consultá el recuento de votos y los comentarios recibidos.</p></div>{% if not selected %}<section class="panel">{% if surveys %}<div class="list">{% for s in surveys %}<div class="list-item"><div><div class="item-title">{{ s.title }}</div><span class="item-meta">Encuesta académica</span></div><a class="btn btn-secondary btn-small" href="/?view=admin_surveys&survey_id={{ s.id }}">Ver resultados&nbsp; →</a></div>{% endfor %}</div>{% else %}<div class="empty-state"><div class="empty-icon">≡</div>No hay encuestas creadas todavía.</div>{% endif %}</section>{% endif %}
{% if selected %}<a href="/?view=admin_surveys" class="back-link">← Volver a encuestas</a><section class="panel"><h3>{{ selected.title }}</h3><h4>Votos por opción</h4><table><tr><th>Opción</th><th>Cantidad de votos</th></tr>{% for r in admin_results[selected.id] %}<tr><td>{{ r.label }}</td><td><b>{{ r.count }}</b></td></tr>{% endfor %}</table><h4>Comentarios anónimos</h4>{% if admin_comments[selected.id] %}{% for comment in admin_comments[selected.id] %}<div class="comment-card">{{ comment.content | safe }}</div>{% endfor %}{% else %}<p class="muted">Todavía no hay comentarios.</p>{% endif %}</section>{% endif %}
{% elif view == 'logs' %}<div class="page-heading"><p class="eyebrow">Administración / Auditoría</p><h1>Actividad del sistema</h1><p class="subtitle">Consultá el registro de acciones relevantes realizadas en las encuestas.</p></div><section class="panel"><h3>Registro de actividad</h3><p class="muted">El archivo contiene eventos funcionales, como creación de encuestas y registro de votos.</p><a href="/admin/logs?file=activity.log" target="_blank" class="btn">Abrir log de actividad&nbsp; ↗</a></section>{% endif %}
{% else %}
{% if completed %}<section class="box" style="max-width:720px;margin:20px auto;text-align:center"><div class="empty-icon" style="background:#e8f7f2;color:#087e6e">✓</div><p class="eyebrow" style="color:#087e6e">Respuesta registrada</p><h1 style="font-size:26px">¡Encuesta completada!</h1><p class="subtitle" style="margin:10px auto 22px">Tu respuesta fue registrada correctamente. Gracias por participar.</p><a class="btn" href="/?view=pending">Volver a encuestas pendientes</a></section>
{% elif view == 'home' %}<div class="page-heading"><p class="eyebrow">Mi espacio</p><h1>Hola, {{ user.username }}</h1><p class="subtitle">Desde acá podés gestionar tus encuestas y consultar las respuestas que ya enviaste.</p></div><div class="stat-grid"><a class="stat-card" href="/?view=pending"><span class="stat-label">Para responder</span><span class="stat-value">{{ pending|length }}</span><span class="muted">Encuestas pendientes →</span></a><a class="stat-card" href="/?view=answered"><span class="stat-label">Tu actividad</span><span class="stat-value">{{ answered|length }}</span><span class="muted">Encuestas respondidas →</span></a></div>
{% elif view == 'pending' and not selected %}<div class="page-heading"><p class="eyebrow">Mis encuestas</p><h1>Encuestas pendientes</h1><p class="subtitle">Estas encuestas todavía están esperando tu respuesta.</p></div><section class="panel">{% if pending %}<div class="list">{% for s in pending %}<div class="list-item"><div><div class="item-title">{{ s.title }}</div><span class="item-meta">Encuesta pendiente de respuesta</span></div><a class="btn btn-small" href="/survey/{{ s.id }}?view=pending">Responder&nbsp; →</a></div>{% endfor %}</div>{% else %}<div class="empty-state"><div class="empty-icon">✓</div>No tenés encuestas pendientes.<br><span class="muted">¡Ya respondiste todas las disponibles!</span></div>{% endif %}</section>
{% elif view == 'answered' and not selected %}<div class="page-heading"><p class="eyebrow">Mis encuestas</p><h1>Encuestas respondidas</h1><p class="subtitle">Consultá las respuestas que registraste anteriormente.</p></div><section class="panel">{% if answered %}<div class="list">{% for s in answered %}<div class="list-item"><div><div class="item-title">{{ s.title }}</div><span class="item-meta">Respuesta enviada</span></div><a class="btn btn-secondary btn-small" href="/survey/{{ s.id }}?view=answered">Ver respuesta&nbsp; →</a></div>{% endfor %}</div>{% else %}<div class="empty-state"><div class="empty-icon">☷</div>Todavía no respondiste ninguna encuesta.</div>{% endif %}</section>{% endif %}
{% if selected and view == 'pending' and not completed %}<a href="/?view=pending" class="back-link">← Volver a encuestas pendientes</a><div class="page-heading"><p class="eyebrow">Encuestas / Responder</p><h1>{{ selected.title }}</h1><p class="subtitle">Seleccioná una opción. Si querés, podés agregar un comentario adicional.</p></div><section class="panel"><form action="/complete-survey" method="POST"><input type="hidden" name="survey_id" value="{{ selected.id }}"><h3>Tu respuesta</h3>{% for choice in choices %}<label class="choice-row"><input type="radio" name="choice_id" value="{{ choice.id }}" required> {{ choice.label }}</label>{% endfor %}<h4>Comentario adicional <span class="muted" style="font-weight:400">(opcional)</span></h4><p class="muted">Este comentario acompaña tu respuesta y será visible para el equipo administrador de forma anónima.</p><textarea name="content" placeholder="Escribí tu comentario aquí..."></textarea><button type="submit" class="btn">Enviar respuesta</button></form></section>
{% elif selected and view == 'answered' %}<a href="/?view=answered" class="back-link">← Volver a encuestas respondidas</a><div class="page-heading"><p class="eyebrow">Mis encuestas / Respuesta enviada</p><h1>{{ selected.title }}</h1><p class="subtitle">Este es el detalle de tu respuesta registrada.</p></div><section class="panel"><h3>Tu respuesta</h3><p>{{ own_choice }}</p>{% if own_comment %}<h4>Tu comentario adicional</h4><div class="comment-card">{{ own_comment | safe }}</div>{% else %}<p class="muted">No agregaste un comentario.</p>{% endif %}</section>{% endif %}
{% endif %}
</main><footer class="footer"><div class="footer-inner"><span>Portal Universitario · Sistema de encuestas académicas</span><a href="/reset" class="btn btn-small reset-demo" onclick="return confirm('¿Reiniciar la demo? Se borrarán los votos, comentarios y encuestas creadas, y se restaurarán los datos iniciales.')">↻ Reiniciar demo</a></div></footer></body></html>"""


# ==========================================
# 4. RUTAS
# ==========================================
# Registro de acciones HTTP relevantes. Las consultas SQL se registran en DEBUG
# mediante set_trace_callback en cada conexión SQLite.
@app.before_request
def log_request_start():
    user = get_current_user()
    username = user.get("username", "anónimo") if user else "anónimo"
    app.logger.info("Solicitud iniciada: %s %s | usuario=%s", request.method, request.path, username)


@app.after_request
def log_request_end(response):
    level = logging.ERROR if response.status_code >= 500 else logging.WARNING if response.status_code >= 400 else logging.INFO
    app.logger.log(level, "Solicitud finalizada: %s %s | status=%s", request.method, request.path, response.status_code)
    return response


@app.route("/")
def index():
    user = get_current_user()
    conn = db_connection()
    surveys = conn.execute("SELECT id, title FROM surveys ORDER BY id").fetchall()
    view = request.args.get("view", "home")
    selected_id = request.args.get("survey_id", type=int)
    selected = conn.execute("SELECT id, title FROM surveys WHERE id=?", (selected_id,)).fetchone() if selected_id else None
    pending, answered = [], []
    admin_results, admin_comments = {}, {}
    own_choice, own_comment = None, None
    choices = []
    completed = request.args.get("completed") == "1"

    if user and user.get("role") == "admin":
        for survey in surveys:
            admin_results[survey["id"]] = conn.execute("""SELECT ch.label, COUNT(v.id) AS count FROM choices ch
                LEFT JOIN votes v ON v.choice_id=ch.id AND v.survey_id=ch.survey_id
                WHERE ch.survey_id=? GROUP BY ch.id, ch.label ORDER BY ch.id""", (survey["id"],)).fetchall()
            admin_comments[survey["id"]] = conn.execute("SELECT content FROM comments WHERE survey_id=? ORDER BY id", (survey["id"],)).fetchall()
    elif user:
        username = user.get("username", "")
        for survey in surveys:
            vote = conn.execute("SELECT id FROM votes WHERE survey_id=? AND username=? LIMIT 1", (survey["id"], username)).fetchone()
            (answered if vote else pending).append(survey)
        if selected and view in ("pending", "answered"):
            vote = conn.execute("""SELECT v.choice_id, ch.label FROM votes v JOIN choices ch ON ch.id=v.choice_id
                WHERE v.survey_id=? AND v.username=? LIMIT 1""", (selected["id"], username)).fetchone()
            if view == "pending" and vote:
                # No permitir que una encuesta ya respondida se abra desde pendientes.
                selected = None
            elif view == "answered" and not vote:
                selected = None
            else:
                own_choice = vote["label"] if vote else None
                choices = conn.execute("SELECT id, label FROM choices WHERE survey_id=? ORDER BY id", (selected["id"],)).fetchall()
                comment = conn.execute("SELECT content FROM comments WHERE survey_id=? AND author=?", (selected["id"], username)).fetchone()
                own_comment = comment["content"] if comment else None
    conn.close()
    response = make_response(render_template_string(HTML_TEMPLATE, user=user, surveys=surveys, view=view,
        pending=pending, answered=answered, selected=selected, choices=choices,
        own_choice=own_choice, own_comment=own_comment, admin_results=admin_results,
        admin_comments=admin_comments, completed=completed, login_error=request.args.get("login_error") == "1"))
    # Si quedó una cookie vieja en el navegador, borrarla al mostrar el login.
    if request.cookies.get("SESSION_TOKEN") and not user:
        response.delete_cookie("SESSION_TOKEN", path="/")
    return response


@app.route("/survey/<int:survey_id>")
def survey_detail(survey_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("index"))
    view = request.args.get("view", "pending")
    conn = db_connection()
    survey = conn.execute("SELECT id FROM surveys WHERE id=?", (survey_id,)).fetchone()
    if not survey:
        conn.close()
        return "Encuesta no encontrada", 404
    if user.get("role") == "admin":
        conn.close()
        return redirect(url_for("index", view="admin_surveys", survey_id=survey_id))
    voted = conn.execute("SELECT id FROM votes WHERE survey_id=? AND username=?", (survey_id, user.get("username"))).fetchone()
    conn.close()
    if view == "answered" and voted:
        return redirect(url_for("index", view="answered", survey_id=survey_id))
    if voted:
        return redirect(url_for("index", view="answered", survey_id=survey_id))
    return redirect(url_for("index", view="pending", survey_id=survey_id))


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "").strip()

    # Cuentas de alumnos para la demo. Todas comparten la contraseña 1234.
    student_accounts = {
        "fede": "9876543210",
        "luciana": "9876543211",
        "tomas": "9876543212",
        "ignacio": "9876543213",
    }

    if username in student_accounts and password == "1234":
        token = create_unsigned_jwt(student_accounts[username], username, "alumno")
    elif username == "admin" and password == "admin123":
        token = create_unsigned_jwt("1234567890", "admin", "admin")
    else:
        app.logger.warning("Intento de login fallido para usuario=%s", username)
        return redirect(url_for("index", login_error=1)), 303

    role = "admin" if username == "admin" else "alumno"
    app.logger.info("Inicio de sesión exitoso: usuario=%s rol=%s", username, role)
    resp = make_response(redirect(url_for("index")))
    # Intencionalmente inseguro para la demostración del laboratorio.
    resp.set_cookie("SESSION_TOKEN", token, httponly=False, path="/")
    return resp


@app.route("/logout")
def logout():
    resp = make_response(redirect(url_for("index")))
    resp.delete_cookie("SESSION_TOKEN", path="/")
    app.logger.info("Cierre de sesión solicitado")
    return resp


@app.route("/complete-survey", methods=["POST"])
def complete_survey():
    user = get_current_user()
    if not user:
        return "No autenticado", 401
    if user.get("role") == "admin":
        return "El administrador no puede responder encuestas desde este panel", 403
    survey_id = request.form.get("survey_id", type=int)
    choice_id = request.form.get("choice_id", type=int)
    content = request.form.get("content", "").strip()
    if not survey_id or not choice_id:
        return "Encuesta u opción inválida", 400
    conn = db_connection()
    choice = conn.execute("SELECT id FROM choices WHERE id=? AND survey_id=?", (choice_id, survey_id)).fetchone()
    existing = conn.execute("SELECT id FROM votes WHERE survey_id=? AND username=?", (survey_id, user.get("username"))).fetchone()
    if not choice:
        conn.close()
        return "La opción no pertenece a esa encuesta", 400
    if existing:
        conn.close()
        return redirect(url_for("index", view="answered", survey_id=survey_id))
    conn.execute("INSERT INTO votes (vote_token, survey_id, choice_id, username) VALUES (?, ?, ?, ?)",
                 (os.urandom(5).hex(), survey_id, choice_id, user.get("username")))
    survey_row = conn.execute("SELECT title FROM surveys WHERE id=?", (survey_id,)).fetchone()
    vote_count = conn.execute("SELECT COUNT(*) AS total FROM votes WHERE survey_id=?", (survey_id,)).fetchone()["total"]
    option_counts = conn.execute(
        """SELECT choices.label, COUNT(votes.id) AS total
           FROM choices
           LEFT JOIN votes ON votes.choice_id = choices.id AND votes.survey_id = choices.survey_id
           WHERE choices.survey_id = ?
           GROUP BY choices.id, choices.label
           ORDER BY choices.id""",
        (survey_id,),
    ).fetchall()
    survey_title = survey_row["title"] if survey_row else "Encuesta"
    breakdown = "; ".join(f"{row['label']}: {row['total']}" for row in option_counts)
    app.logger.info(
        "Voto registrado: usuario=%s encuesta=%s total_votos=%s distribución=[%s]",
        user.get("username"), survey_title, vote_count, breakdown
    )
    log_activity(
        f"Nuevo voto registrado en «{survey_title}». "
        f"Votos por opción: {breakdown}. Total de votos contabilizados: {vote_count}."
    )
    if content:
        # Puede existir un comentario de demostración para este usuario y encuesta.
        # En ese caso, actualizarlo evita violar UNIQUE(survey_id, author).
        existing_comment = conn.execute(
            "SELECT id FROM comments WHERE survey_id=? AND author=?",
            (survey_id, user.get("username")),
        ).fetchone()
        if existing_comment:
            conn.execute(
                "UPDATE comments SET content=? WHERE id=?",
                (content, existing_comment["id"]),
            )
            app.logger.info("Comentario existente actualizado para la encuesta=%s", survey_title)
        else:
            conn.execute(
                "INSERT INTO comments (survey_id, author, content) VALUES (?, ?, ?)",
                (survey_id, user.get("username"), content),
            )
            app.logger.info("Comentario registrado para la encuesta=%s", survey_title)
    conn.commit()
    conn.close()
    return redirect(url_for("index", view="pending", completed=1))


@app.route("/vote", methods=["POST"])
def vote():
    user = get_current_user()
    if not user:
        return "No autenticado", 401
    if user.get("role") == "admin":
        return "El administrador no puede responder encuestas desde este panel", 403
    survey_id = request.form.get("survey_id", type=int)
    choice_id = request.form.get("choice_id", type=int)
    if not survey_id or not choice_id:
        return "Encuesta u opción inválida", 400
    conn = db_connection()
    choice = conn.execute("SELECT id FROM choices WHERE id=? AND survey_id=?", (choice_id, survey_id)).fetchone()
    existing = conn.execute("SELECT id FROM votes WHERE survey_id=? AND username=?", (survey_id, user.get("username"))).fetchone()
    if not choice:
        conn.close()
        return "La opción no pertenece a esa encuesta", 400
    if existing:
        conn.close()
        return "Ya respondiste esta encuesta", 409
    conn.execute("INSERT INTO votes (vote_token, survey_id, choice_id, username) VALUES (?, ?, ?, ?)",
                 (os.urandom(5).hex(), survey_id, choice_id, user.get("username")))
    conn.commit()
    conn.close()
    return redirect(url_for("index", view="answered", survey_id=survey_id))


@app.route("/comment", methods=["POST"])
def add_comment():
    user = get_current_user()
    if not user:
        return "No autenticado", 401
    if user.get("role") == "admin":
        return "El administrador no puede comentar encuestas desde este panel", 403
    survey_id = request.form.get("survey_id", type=int)
    content = request.form.get("content", "").strip()
    if not survey_id or not content:
        return "El comentario no puede estar vacío", 400
    conn = db_connection()
    voted = conn.execute("SELECT id FROM votes WHERE survey_id=? AND username=?", (survey_id, user.get("username"))).fetchone()
    if not voted:
        conn.close()
        return "Primero tenés que responder la encuesta", 403
    existing = conn.execute("SELECT id FROM comments WHERE survey_id=? AND author=?", (survey_id, user.get("username"))).fetchone()
    if existing:
        conn.close()
        return "Ya dejaste un comentario para esta encuesta", 409
    try:
        conn.execute("INSERT INTO comments (survey_id, author, content) VALUES (?, ?, ?)",
                     (survey_id, user.get("username"), content))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return "Ya dejaste un comentario para esta encuesta", 409
    conn.close()
    return redirect(url_for("index", view="answered", survey_id=survey_id))


@app.route("/admin/surveys/create", methods=["POST"])
def create_survey():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return "403 Forbidden - Se requiere rol de administrador", 403
    title = request.form.get("title", "").strip()
    options = [line.strip() for line in request.form.get("choices", "").splitlines() if line.strip()]
    if not title or len(options) < 2:
        return "Ingresá una pregunta y al menos dos opciones", 400
    conn = db_connection()
    cur = conn.execute("INSERT INTO surveys (title) VALUES (?)", (title,))
    survey_id = cur.lastrowid
    conn.executemany("INSERT INTO choices (survey_id, label) VALUES (?, ?)", [(survey_id, option) for option in options])
    app.logger.info("Encuesta creada: admin=%s encuesta=%s cantidad_opciones=%s", user.get("username"), title, len(options))
    log_activity(f"Nueva encuesta creada: «{title}».")
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


# PASO 3 del laboratorio: Path Traversal intencional.
@app.route("/admin/logs")
def admin_logs():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return "403 Forbidden - Se requiere rol de Administrador de Facultad", 403
    filename = request.args.get("file", "activity.log")
    filepath = os.path.join(PUBLIC_LOGS_DIR, filename)
    if not os.path.exists(filepath):
        return f"Archivo no encontrado: {filename}", 404
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    resp = make_response(content, 200)
    resp.mimetype = "text/plain"
    return resp


# Endpoint intencionalmente vulnerable para el ejercicio de SQL Injection.
@app.route("/api/admin/votes")
def api_admin_votes():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return jsonify({"error": "403 Forbidden - Acceso exclusivo para administradores"}), 403
    vote_id = request.args.get("vote_id", "1")
    raw_query = f"SELECT id, vote_token, survey_id, choice_id FROM votes WHERE id = {vote_id}"
    conn = sqlite3.connect(DB_NAME)
    conn.set_trace_callback(lambda sql: app.logger.debug("SQL: %s", sql))
    c = conn.cursor()
    try:
        app.logger.debug("SQL endpoint /api/admin/votes: %s", raw_query)
        clean_query = raw_query.split("--")[0]
        statements = [s.strip() for s in clean_query.split(";") if s.strip()]
        first_row = None
        for idx, stmt in enumerate(statements):
            c.execute(stmt)
            if idx == 0:
                first_row = c.fetchone()
        conn.commit()
    except Exception as e:
        app.logger.exception("Error ejecutando consulta del endpoint vulnerable /api/admin/votes")
        conn.close()
        return jsonify({"sql_error": str(e), "executed_query": raw_query}), 500
    conn.close()
    if first_row:
        return jsonify({"vote_id": first_row[0], "vote_token": first_row[1], "survey_id": first_row[2], "choice_id": first_row[3]})
    return jsonify({"message": "Sin resultados", "data": None}), 200


@app.route("/reset")
def reset():
    init_environment()
    resp = make_response(redirect(url_for("index")))
    resp.delete_cookie("SESSION_TOKEN", path="/")
    return resp


if __name__ == "__main__":
    init_environment()
    app.logger.info("Servidor iniciado en http://127.0.0.1:5000")
    print("[*] Entorno inicializado. Corriendo en http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
