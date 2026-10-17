# TP Seguridad en Aplicaciones Web - Grupo N°4

Laboratorio práctico para la demostración de vulnerabilidades encadenadas en una plataforma de encuestas universitarias[cite: 1, 2].

**Integrantes:**
* Herrera, Federico (`feherrera@frba.utn.edu.ar`)[cite: 1]
* Napolillo, Luciana (`lnapolillo@frba.utn.edu.ar`)[cite: 1]
* Rodríguez, Ignacio (`irodriguezmartin@frba.utn.edu.ar`)[cite: 1]
* Rosman, Tomas (`tomasrosman@frba.utn.edu.ar`)[cite: 1]

**Profesores:** Ing. Vilanova, Gonzalo | Ing. Fuentes, Nicolás | Novoa, Germán | Berruto, Maximiliano[cite: 1]

---

## 🛠️ Parte 1: Cómo dejar listo el laboratorio (Previa)

Toda la plataforma corre en un único archivo (`app.py`) que crea automáticamente la base de datos SQLite y los archivos de log necesarios[cite: 4, 7].

### 1. Clonar el repositorio e instalar Flask
En Kali Linux (o cualquier distribución basada en Debian/Ubuntu):
```bash
git clone https://github.com/ignacioRodriguezM/tpGrupo4Seguridad.git
cd tpGrupo4Seguridad
sudo apt update && sudo apt install -y python3-flask
