import base64
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from http.cookies import SimpleCookie
from urllib.parse import urlparse, parse_qs


# Configuración del logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def decode_jwt(token):
    """
    Decodifica el header y el payload de un JWT.
    No valida su firma ni verifica su autenticidad.
    """
    parts = token.split(".")

    if len(parts) != 3:
        raise ValueError("El JWT debe tener tres partes")

    def decode_part(part):
        # Base64 URL-safe requiere padding múltiplo de 4
        padding = "=" * (-len(part) % 4)
        decoded = base64.urlsafe_b64decode(part + padding)
        return json.loads(decoded.decode("utf-8"))

    header = decode_part(parts[0])
    payload = decode_part(parts[1])

    return {
        "header": header,
        "payload": payload
    }


class RequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path != "/log":
            self.send_error(404, "Endpoint no encontrado")
            return

        query_params = parse_qs(parsed_url.query)
        cookie_values = query_params.get("cookie")

        if not cookie_values:
            self.send_error(400, "Falta el parámetro cookie")
            return

        cookie_value = cookie_values[0]

        try:
            # El parámetro puede contener la cookie completa
            # o directamente el JWT.
            if cookie_value.startswith("SESSION_TOKEN="):
                cookie = SimpleCookie()
                cookie.load(cookie_value)

                if "SESSION_TOKEN" not in cookie:
                    raise ValueError("No se encontró SESSION_TOKEN")

                token = cookie["SESSION_TOKEN"].value
            else:
                token = cookie_value

            decoded_jwt = decode_jwt(token)

            # Registramos el contenido decodificado, no el token original.
            logger.info(
                "JWT decodificado: %s",
                json.dumps(decoded_jwt, ensure_ascii=False, separators=(",", ":"))
            )

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            response = {
                "status": "ok",
                "message": "JWT decodificado correctamente"
            }

            self.wfile.write(
                json.dumps(response).encode("utf-8")
            )

        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            logger.warning("No se pudo decodificar el JWT: %s", error)
            self.send_error(400, "Cookie o JWT inválido")

    def log_message(self, format_string, *args):
        # Evita que el servidor registre la URL completa,
        # que podría contener el JWT.
        logger.info(
            "%s - %s",
            self.client_address[0],
            format_string % args
        )


if __name__ == "__main__":
    server_address = ("127.0.0.1", 8080)
    httpd = HTTPServer(server_address, RequestHandler)

    logger.info("Servidor escuchando en http://127.0.0.1:8080")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Cerrando servidor")
    finally:
        httpd.server_close()