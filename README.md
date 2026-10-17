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

## 🛠️ Parte 1: Cómo dejar listo el laboratorio (Previa)

Toda la plataforma crea automáticamente la base de datos y los archivos de log necesarios al inicializarse.

### 1. Clonar el repositorio e instalar Flask
En Kali Linux (o cualquier distribución basada en Debian/Ubuntu):
```bash
git clone https://github.com/ignacioRodriguezM/tpGrupo4Seguridad.git
cd tpGrupo4Seguridad
sudo apt update && sudo apt install -y python3-flask
