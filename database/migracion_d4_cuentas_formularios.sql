-- ========================================================
-- B.A.W.I. - Migracion D4: verificar correo, editar publicaciones y Formularios
-- Ejecutar UNA vez en SSMS sobre la base existente (no borra datos). Se puede volver a correr.
-- Despues, cargar los formularios con:  python -m backend.seed_formularios
-- ========================================================
USE bawi;
GO

-- 1. Cuentas esperando el codigo de verificacion del correo
IF OBJECT_ID('registros_pendientes', 'U') IS NULL
BEGIN
    CREATE TABLE registros_pendientes (
        correo NVARCHAR(120) PRIMARY KEY,
        nombre NVARCHAR(80) NOT NULL,
        municipio NVARCHAR(60) NOT NULL,
        password_hash NVARCHAR(255) NOT NULL,
        codigo_hash NVARCHAR(64) NOT NULL,
        intentos TINYINT NOT NULL DEFAULT 0,
        enviado_en DATETIME NOT NULL,
        expira_en DATETIME NOT NULL
    );
END
GO

-- 2. Marca de "editada" en publicaciones
IF COL_LENGTH('publicaciones', 'editada_en') IS NULL
    ALTER TABLE publicaciones ADD editada_en DATETIME NULL;
GO

-- 3. Formularios: codigo (N1-F01), caso, estado de revision y fuentes por pregunta
IF COL_LENGTH('quizzes', 'codigo') IS NULL
    ALTER TABLE quizzes ADD codigo NVARCHAR(10) NULL;
IF COL_LENGTH('quizzes', 'contexto') IS NULL
    ALTER TABLE quizzes ADD contexto NVARCHAR(MAX) NULL;
IF COL_LENGTH('quizzes', 'estado') IS NULL
    ALTER TABLE quizzes ADD estado NVARCHAR(12) NOT NULL CONSTRAINT df_quizzes_estado DEFAULT 'aprobada';
IF COL_LENGTH('preguntas', 'fuentes') IS NULL
    ALTER TABLE preguntas ADD fuentes NVARCHAR(40) NULL;
GO

-- 4. Verificacion: 1 tabla y 5 columnas
SELECT name AS tabla_nueva FROM sys.tables WHERE name = 'registros_pendientes';
SELECT TABLE_NAME AS tabla, COLUMN_NAME AS columna_nueva FROM INFORMATION_SCHEMA.COLUMNS
WHERE (TABLE_NAME = 'publicaciones' AND COLUMN_NAME = 'editada_en')
   OR (TABLE_NAME = 'quizzes' AND COLUMN_NAME IN ('codigo', 'contexto', 'estado'))
   OR (TABLE_NAME = 'preguntas' AND COLUMN_NAME = 'fuentes');
GO