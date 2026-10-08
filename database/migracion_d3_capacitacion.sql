-- ========================================================
-- B.A.W.I. - Migracion D3: Capacitacion
-- Agrega dos columnas que usan las dinamicas:
--   preguntas.pista  -> ayuda que se muestra cuando la respuesta es incorrecta
--   quizzes.ejemplo  -> ejemplo de campo de la tarjeta "Conoce una palabra"
-- Ejecutar UNA vez en SSMS sobre la base existente (no borra datos).
-- Se puede volver a correr sin problema.
-- Despues, cargar el contenido con:  python -m backend.seed_capacitacion
-- ========================================================
USE bawi;
GO

IF COL_LENGTH('preguntas', 'pista') IS NULL
    ALTER TABLE preguntas ADD pista NVARCHAR(400) NULL;
GO

IF COL_LENGTH('quizzes', 'ejemplo') IS NULL
    ALTER TABLE quizzes ADD ejemplo NVARCHAR(400) NULL;
GO

-- Verificacion: deben salir las dos columnas
SELECT TABLE_NAME AS tabla, COLUMN_NAME AS columna_nueva
FROM INFORMATION_SCHEMA.COLUMNS
WHERE (TABLE_NAME = 'preguntas' AND COLUMN_NAME = 'pista')
   OR (TABLE_NAME = 'quizzes' AND COLUMN_NAME = 'ejemplo');
GO