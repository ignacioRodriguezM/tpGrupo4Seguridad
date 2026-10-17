# TP Seguridad en Aplicaciones Web - Grupo N°4

Laboratorio práctico para la demostración de vulnerabilidades encadenadas en una plataforma de encuestas universitarias.

**Universidad Tecnológica Nacional - Facultad Regional Buenos Aires (UTN.BA)**

**Integrantes:**
* Herrera, Federico (`feherrera@frba.utn.edu.ar`)
* Napolillo, Luciana (`lnapolillo@frba.utn.edu.ar`)
* Rodríguez, Ignacio (`irodriguezmartin@frba.utn.edu.ar`)
* Rosman, Tomas (`tomasrosman@frba.utn.edu.ar`)

**Profesores:** Ing. Vilanova, Gonzalo | Ing. Fuentes, Nicolás | Novoa, Germán | Berruto, Maximiliano

---

## 🏗️ Arquitectura y Tecnologías

Para que el laboratorio sea autocontenido, fácil de auditar y no requiera de contenedores Docker ni motores externos pesados, el sistema se diseñó bajo una **arquitectura monolítica simple (Cliente-Servidor)** concentrada en un único archivo ejecutable (`app.py`).

### Stack Tecnológico
* **Lenguaje Backend:** Python 3.
* **Framework Web:** Flask (encargado del enrutamiento HTTP, lógica de negocio y renderizado de plantillas).
* **Base de Datos:** SQLite 3 (motor embebido relacional que autogenera el archivo `universidad.db` en el mismo directorio).
* **Frontend:** HTML5, CSS3 y JavaScript vanilla integrados directamente mediante el motor de plantillas Jinja2 de Flask.
* **Herramientas del Atacante:** Netcat (`nc`) para la escucha de peticiones por red y DevTools del navegador para manipulación de cookies.

### Flujo de Datos y Ejecución
1. **Flujo Normal:** El cliente (navegador) realiza una petición HTTP al puerto `5000`. Flask intercepta la ruta, consulta a la base de datos SQLite (para validar sesión, leer encuestas o guardar comentarios) y devuelve un documento HTML renderizado al cliente.
2. **Flujo del Ataque:** El servidor almacena un payload malicioso en SQLite como texto plano (comentario). Cuando la víctima (Administrador) solicita la página, Flask incrusta ese texto en el HTML sin sanitizar. El navegador de la víctima interpreta el texto como JavaScript (`<script>`) y dispara una petición HTTP asíncrona (`fetch()`) hacia el servicio de escucha del atacante (puerto `8080`), exfiltrando su token de sesión temporal.

---

## 🛠️ Cómo dejar listo el laboratorio (Previa)

Toda la plataforma crea automáticamente la base de datos y los archivos de log necesarios al inicializarse.

### 1. Clonar el repositorio e instalar Flask
En Kali Linux (o cualquier distribución basada en Debian/Ubuntu):
```bash
git clone https://github.com/ignacioRodriguezM/tpGrupo4Seguridad.git
cd tpGrupo4Seguridad
sudo apt update && sudo apt install -y python3-flask

### 2. Levantar el servidor web
python3 app.py
```
El servidor quedará corriendo en **`http://localhost:5000`**. Dejen esa terminal abierta.

### 3. Preparar las ventanas para la presentación
Antes de empezar a exponer, dejen abiertas estas **3 herramientas**:
1. **Navegador Ventana Normal:** En `http://localhost:5000` (acá usamos al alumno atacante **`fede`**).
2. **Navegador Ventana de Incógnito:** En `http://localhost:5000` (acá usamos a la víctima **`admin`**; obligatorio usar Incógnito para no pisar las cookies).
3. **Una segunda terminal vacía:** Lista para correr el listener de Netcat (`nc -lvnp 8080`) en el Paso 2.

> 💡 **Botón salvavidas:** Arriba a la derecha en la página hay un botón gris de **"Reiniciar Demo"**. Tocarlo restaura todos los votos y comentarios a su estado inicial.

---

## 🛡️ Cómo mitigar cada vulnerabilidad

| Vulnerabilidad | Causa en el código (`app.py`) | Solución en Producción |
| :--- | :--- | :--- |
| **1. Stored XSS** | Uso de `\| safe` en Jinja2 para renderizar comentarios. | Quitar `\| safe` para que el framework escape automáticamente los caracteres HTML, e implementar Content-Security-Policy (CSP). |
| **2. Session Hijacking** | Cookie sin `HttpOnly` y JWT con `alg: none`. | Configurar cookie con `HttpOnly=True` y `Secure=True`. Firmar los JWT (`HS256`/`RS256`) y rechazar tokens sin firma. |
| **3. Path Traversal** | Concatenación directa del parámetro `file`. | Usar `os.path.basename(file)` y validar contra una lista blanca estricta (ej. `if file != "activity.log": abort(403)`). |
| **4. SQL Injection + Broken Access** | Concatenación directa en strings SQL y endpoint huérfano. | Eliminar rutas de debug en producción y usar **Consultas Parametrizadas** (`execute("... WHERE id = ?", (id,))`) que evitan las Stacked Queries. |
