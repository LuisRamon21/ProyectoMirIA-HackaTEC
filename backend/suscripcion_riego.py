"""
Activa o desactiva la suscripcion de pago de B.A.W.I. Riego de una cuenta.

La cuenta se crea en la app (Riego o Comunidad). Cuando el productor paga, se activa
su suscripcion y ya puede entrar a Riego y registrar sus parcelas.

Ejecutar desde la raiz del proyecto:
    python -m backend.suscripcion_riego --lista
    python -m backend.suscripcion_riego --activar productor@correo.com
    python -m backend.suscripcion_riego --desactivar productor@correo.com
(tambien se acepta el nombre de usuario en lugar del correo)
"""
import argparse

from sqlalchemy import text

from backend.db import engine


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Suscripcion de B.A.W.I. Riego.")
    accion = p.add_mutually_exclusive_group(required=True)
    accion.add_argument("--activar", metavar="CORREO", help="activa la suscripcion de la cuenta")
    accion.add_argument("--desactivar", metavar="CORREO", help="quita la suscripcion de la cuenta")
    accion.add_argument("--lista", action="store_true", help="muestra las cuentas con Riego activo")
    return p.parse_args()


def cambiar(cuenta: str, activa: bool) -> None:
    with engine.begin() as conexion:
        fila = conexion.execute(
            text("SELECT id_usuario, nombre FROM usuarios WHERE correo = :c OR usuario = :c"),
            {"c": cuenta.strip().lower()},
        ).first()
        if fila is None:
            raise SystemExit(f"No existe una cuenta con el correo o usuario '{cuenta}'.")
        conexion.execute(text("UPDATE usuarios SET suscripcion_riego = :a WHERE id_usuario = :u"),
                         {"a": int(activa), "u": fila.id_usuario})
    print(f"B.A.W.Í. Riego {'activado' if activa else 'desactivado'} para {fila.nombre} ({cuenta}).")


def lista() -> None:
    with engine.connect() as conexion:
        filas = conexion.execute(
            text("SELECT u.nombre, u.correo, u.usuario, COUNT(p.id_parcela) AS parcelas FROM usuarios u "
                 "LEFT JOIN parcelas p ON p.id_usuario = u.id_usuario WHERE u.suscripcion_riego = 1 "
                 "GROUP BY u.nombre, u.correo, u.usuario ORDER BY u.nombre")
        ).all()
    if not filas:
        print("Ninguna cuenta tiene B.A.W.Í. Riego activo.")
    for f in filas:
        print(f"  {f.nombre} - {f.correo or f.usuario} - {f.parcelas} parcela(s)")


if __name__ == "__main__":
    a = _argumentos()
    if a.lista:
        lista()
    else:
        cambiar(a.activar or a.desactivar, activa=bool(a.activar))
