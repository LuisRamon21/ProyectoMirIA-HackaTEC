-- ========================================================
-- B.A.W.I. - Migracion D2: likes en publicaciones y puntos de demo
-- Ejecutar UNA vez en SSMS sobre la base existente (no borra datos).
-- Se puede volver a correr sin problema: revisa antes de crear o cambiar.
-- ========================================================
USE bawi;
GO

-- 1. Likes de publicaciones (no dan puntos; ordenan "Tendencias")
IF OBJECT_ID('likes_publicacion', 'U') IS NULL
BEGIN
    CREATE TABLE likes_publicacion (
        id_like INT PRIMARY KEY IDENTITY(1,1),
        id_publicacion INT NOT NULL,
        id_usuario INT NOT NULL,
        creado_en DATETIME DEFAULT GETDATE(),
        CONSTRAINT uq_like_publicacion UNIQUE (id_publicacion, id_usuario),
        FOREIGN KEY (id_publicacion) REFERENCES publicaciones(id_publicacion) ON DELETE CASCADE,
        FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
    );
END
GO

-- 2. Puntos de los usuarios de demo, para que cada uno tenga un rango distinto
--    (don_ramiro es Maestro de la Tierra por usar B.A.W.I. Riego)
UPDATE usuarios SET puntos = 650 WHERE usuario = 'tecnico_beto' AND puntos < 650;  -- Especialista Agronomo
UPDATE usuarios SET puntos = 130 WHERE usuario = 'sofia_campo' AND puntos < 130;   -- Aprendiz del Campo
GO

-- 3. Verificacion
SELECT name AS tabla_nueva FROM sys.tables WHERE name = 'likes_publicacion';
SELECT usuario, puntos, suscripcion_riego FROM usuarios ORDER BY puntos DESC;
GO