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

## Arquitectura

El sistema se diseñó bajo una **arquitectura monolítica simple (Cliente-Servidor)** concentrada en un único archivo ejecutable (`app.py`).

### Stack Tecnológico
* **Lenguaje Backend:** Python 3.
* **Framework Web:** Flask (encargado del enrutamiento HTTP, lógica de negocio y renderizado de plantillas).
* **Base de Datos:** SQLite 3 (motor embebido relacional que autogenera el archivo `universidad.db` en el mismo directorio).
* **Frontend:** HTML5, CSS3 y JavaScript vanilla integrados directamente mediante el motor de plantillas Jinja2 de Flask.
* **Herramientas del Atacante:** `listener.py`, para la escucha de peticiones por red y DevTools del navegador para manipulación de cookies.

### Flujo de Datos y Ejecución
1. **Flujo Normal:** El cliente (navegador) realiza una petición HTTP al puerto `5000`. Flask intercepta la ruta, consulta a la base de datos SQLite (para validar sesión, leer encuestas o guardar comentarios) y devuelve un documento HTML renderizado al cliente.
2. **Flujo del Ataque:** El servidor almacena un payload malicioso en SQLite como texto plano (comentario). Cuando la víctima (Administrador) solicita la página, Flask incrusta ese texto en el HTML sin sanitizar. El navegador de la víctima interpreta el texto como JavaScript (`<script>`) y dispara una petición HTTP asíncrona (`fetch()`) hacia el servicio de escucha del atacante (puerto `8080`), exfiltrando su token de sesión temporal.

---

## Cómo levantar el laboratorio

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

### 3. Ejecución
1. **Navegador Ventana Normal:** En `http://localhost:5000` (acá usamos al alumno atacante **`fede`**).
2. **Navegador Ventana de Incógnito (para no pisar las cookies):** En `http://localhost:5000` (acá usamos a la víctima **`admin`**).
3. **Levantar el listener:
```
python3 listener.py
```
4. Seguir los pasos del documento preliminar

> 💡 **Botón salvavidas:** Abajo a la derecha en la página hay un botón de **"Reiniciar Demo"**. Tocarlo restaura todos los votos y comentarios a su estado inicial.
