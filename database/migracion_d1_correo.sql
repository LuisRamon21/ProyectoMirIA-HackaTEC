-- ========================================================
-- B.A.W.I. - Migracion D1: iniciar sesion con correo
-- Ejecutar UNA vez en SSMS sobre la base existente (no borra datos).
-- Se puede volver a correr sin problema.
-- ========================================================
USE bawi;
GO

-- 1. Columna correo (NULL permitido para cuentas viejas sin correo)
IF COL_LENGTH('usuarios', 'correo') IS NULL
    ALTER TABLE usuarios ADD correo NVARCHAR(120) NULL;
GO

-- 2. Un correo no se puede repetir (los NULL si)
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'uq_usuarios_correo')
    CREATE UNIQUE INDEX uq_usuarios_correo ON usuarios(correo) WHERE correo IS NOT NULL;
GO

-- 3. Correos de las cuentas de demo (contrasena: bawi2026)
UPDATE usuarios SET correo = 'ramiro@bawi.mx' WHERE usuario = 'don_ramiro' AND correo IS NULL;
UPDATE usuarios SET correo = 'beto@bawi.mx' WHERE usuario = 'tecnico_beto' AND correo IS NULL;
UPDATE usuarios SET correo = 'sofia@bawi.mx' WHERE usuario = 'sofia_campo' AND correo IS NULL;
GO

-- 4. Verificacion
SELECT usuario, correo, puntos FROM usuarios ORDER BY id_usuario;
GO
