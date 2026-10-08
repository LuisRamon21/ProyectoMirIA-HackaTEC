-- ========================================================
-- B.A.W.I. - Base de datos en SQL Server (Riego, Comunidad y Capacitacion)
-- Ejecutar en SSMS: Archivo > Abrir > Archivo... > Ejecutar (F5)
--   o en terminal: sqlcmd -S localhost\SQLEXPRESS -E -C -f 65001 -i database\bawi_database.sql
-- OJO: borra la base "bawi" si ya existe y la crea de nuevo.
-- Despues se carga el contenido de Capacitacion (ver README.md).
-- ========================================================

-- ========================================================
-- 1. CREACIÓN Y CONFIGURACIÓN DE LA BASE DE DATOS
-- ========================================================
USE master;
GO
IF EXISTS (SELECT * FROM sys.databases WHERE name = 'bawi')
BEGIN
    ALTER DATABASE bawi SET SINGLE_USER WITH ROLLBACK IMMEDIATE;  -- cierra conexiones abiertas
    DROP DATABASE bawi;
END
GO

CREATE DATABASE bawi;
GO

USE bawi;
GO
-- Necesario para el indice filtrado de correo (sqlcmd los trae apagados por defecto)
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- ========================================================
-- 2. TABLAS Y ESQUEMA PRINCIPAL (Adaptado de bawi_schema.sql)
-- ========================================================

CREATE TABLE rangos (
    id_rango TINYINT PRIMARY KEY,
    nombre NVARCHAR(40) NOT NULL UNIQUE,
    insignia NVARCHAR(8) NOT NULL,
    puntos_min INT NOT NULL,
    puntos_max INT NULL,
    descripcion NVARCHAR(150)
);

-- clave = el texto que usa el codigo (orquestador y apps)
CREATE TABLE cultivos (
    id_cultivo INT PRIMARY KEY IDENTITY(1,1),
    clave NVARCHAR(30) NOT NULL UNIQUE,
    nombre NVARCHAR(60) NOT NULL UNIQUE,
    descripcion NVARCHAR(200) NULL
);

CREATE TABLE clima_diario (
    id_clima INT PRIMARY KEY IDENTITY(1,1),
    municipio NVARCHAR(60) NOT NULL,
    fecha DATE NOT NULL,
    temperatura_c DECIMAL(4,1),
    temp_max_c DECIMAL(4,1),
    temp_min_c DECIMAL(4,1),
    humedad_rel_pct DECIMAL(4,1),
    viento_ms DECIMAL(4,1),
    radiacion_mj_m2 DECIMAL(5,2),
    prob_lluvia_pct TINYINT DEFAULT 0,
    lluvia_mm DECIMAL(5,1) DEFAULT 0,
    et0_mm DECIMAL(4,2) NOT NULL,
    fuente NVARCHAR(30) DEFAULT 'open-meteo',
    consultado_en DATETIME DEFAULT GETDATE(),
    UNIQUE (municipio, fecha)
);

CREATE TABLE tarifas_energia (
    id_tarifa INT PRIMARY KEY IDENTITY(1,1),
    nombre NVARCHAR(20) NOT NULL,
    precio_kwh DECIMAL(6,4) NOT NULL,
    vigente_desde DATE NOT NULL,
    fuente_url NVARCHAR(255)
);

CREATE TABLE usuarios (
    id_usuario INT PRIMARY KEY IDENTITY(1,1),
    nombre NVARCHAR(80) NOT NULL,
    usuario NVARCHAR(30) NOT NULL UNIQUE,
    correo NVARCHAR(120) NULL,
    password_hash NVARCHAR(255) NOT NULL,
    municipio NVARCHAR(60) NOT NULL,
    rol NVARCHAR(20) DEFAULT 'productor' CHECK (rol IN ('productor','tecnico','admin')),
    puntos INT NOT NULL DEFAULT 0,
    suscripcion_riego BIT DEFAULT 0,
    comparte_datos BIT DEFAULT 0,
    foto_ruta NVARCHAR(255) NULL,
    fecha_registro DATETIME DEFAULT GETDATE()
);

-- Correo unico (se permiten varios NULL)
CREATE UNIQUE INDEX uq_usuarios_correo ON usuarios(correo) WHERE correo IS NOT NULL;

-- Cuentas esperando el codigo de verificacion del correo
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

CREATE TABLE etapas_cultivo (
    id_etapa INT PRIMARY KEY IDENTITY(1,1),
    id_cultivo INT NOT NULL,
    clave NVARCHAR(20) NOT NULL,
    nombre NVARCHAR(60) NOT NULL,
    kc DECIMAL(4,2) NOT NULL,
    orden TINYINT NOT NULL,
    UNIQUE (id_cultivo, orden),
    UNIQUE (id_cultivo, clave),
    FOREIGN KEY (id_cultivo) REFERENCES cultivos(id_cultivo)
);

CREATE TABLE quizzes (
    id_quiz INT PRIMARY KEY IDENTITY(1,1),
    titulo NVARCHAR(100) NOT NULL,
    tema NVARCHAR(60) NOT NULL,
    descripcion NVARCHAR(255) NULL,
    id_rango_minimo TINYINT NULL,
    puntos_por_acierto INT DEFAULT 10,
    activo BIT DEFAULT 1,
    ejemplo NVARCHAR(400) NULL,      -- ejemplo de campo de la tarjeta "Conoce una palabra"
    codigo NVARCHAR(10) NULL,        -- codigo del formulario (N1-F01)
    contexto NVARCHAR(MAX) NULL,     -- caso del formulario
    estado NVARCHAR(12) NOT NULL CONSTRAINT df_quizzes_estado DEFAULT 'aprobada',
    FOREIGN KEY (id_rango_minimo) REFERENCES rangos(id_rango)
);

CREATE TABLE parcelas (
    id_parcela INT PRIMARY KEY IDENTITY(1,1),
    id_usuario INT NOT NULL,
    id_cultivo INT NOT NULL,
    id_etapa INT NOT NULL,
    nombre NVARCHAR(60) NOT NULL,
    municipio NVARCHAR(60) NOT NULL,
    latitud DECIMAL(9,6) NULL,
    longitud DECIMAL(9,6) NULL,
    area_ha DECIMAL(8,2) NOT NULL,
    sistema NVARCHAR(30) NOT NULL CHECK (sistema IN ('goteo','microaspersion')),
    tasa_mm_h DECIMAL(5,2) NOT NULL,  -- mm por hora que aplica el sistema (dato de la app de Riego)
    potencia_bomba_kw DECIMAL(6,2) NOT NULL,
    horas_riego_habitual DECIMAL(4,2) NOT NULL,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario),
    FOREIGN KEY (id_cultivo) REFERENCES cultivos(id_cultivo),
    FOREIGN KEY (id_etapa) REFERENCES etapas_cultivo(id_etapa)
);

CREATE TABLE movimientos_puntos (
    id_movimiento INT PRIMARY KEY IDENTITY(1,1),
    id_usuario INT NOT NULL,
    puntos INT NOT NULL,
    motivo NVARCHAR(30) NOT NULL CHECK (motivo IN ('quiz', 'comentario_util', 'publicacion')),
    id_referencia INT NULL,
    fecha DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

CREATE TABLE publicaciones (
    id_publicacion INT PRIMARY KEY IDENTITY(1,1),
    id_usuario INT NOT NULL,
    titulo NVARCHAR(150) NOT NULL,
    texto NVARCHAR(MAX) NOT NULL,
    imagen_ruta NVARCHAR(255) NULL,
    audio_ruta NVARCHAR(255) NULL,
    categoria NVARCHAR(20) DEFAULT 'otro' CHECK (categoria IN ('riego', 'plagas', 'suelo', 'cultivo', 'otro')),
    creada_en DATETIME DEFAULT GETDATE(),
    editada_en DATETIME NULL,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);
GO
CREATE INDEX idx_publicaciones_creada_en ON publicaciones(creada_en);
GO

CREATE TABLE preguntas (
    id_pregunta INT PRIMARY KEY IDENTITY(1,1),
    id_quiz INT NOT NULL,
    enunciado NVARCHAR(MAX) NOT NULL,
    explicacion NVARCHAR(MAX) NOT NULL,
    orden TINYINT NOT NULL,
    pista NVARCHAR(400) NULL,        -- ayuda que se muestra cuando la respuesta es incorrecta
    fuentes NVARCHAR(40) NULL,
    FOREIGN KEY (id_quiz) REFERENCES quizzes(id_quiz) ON DELETE CASCADE
);

CREATE TABLE recomendaciones_riego (
    id_recomendacion INT PRIMARY KEY IDENTITY(1,1),
    id_parcela INT NOT NULL,
    id_clima INT NOT NULL,
    fecha DATE NOT NULL,
    et0_mm DECIMAL(4,2) NOT NULL,
    kc DECIMAL(4,2) NOT NULL,
    etc_mm DECIMAL(4,2) NOT NULL,
    riesgo NVARCHAR(10) NULL,
    factor_reposicion_pct DECIMAL(5,1) NULL,
    lamina_neta_mm DECIMAL(4,2) NOT NULL,
    horas_sugeridas DECIMAL(4,2) NOT NULL,
    explicacion NVARCHAR(MAX) NOT NULL,
    estado NVARCHAR(20) DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aceptada', 'ajustada', 'rechazada')),
    horas_aplicadas DECIMAL(4,2) NULL,
    motivo NVARCHAR(120) NULL,
    agua_ahorrada_m3 DECIMAL(8,2) NULL,
    kwh_ahorrados DECIMAL(8,2) NULL,
    ahorro_mxn DECIMAL(10,2) NULL,
    creada_en DATETIME DEFAULT GETDATE(),
    decidida_en DATETIME NULL,
    UNIQUE (id_parcela, fecha),
    FOREIGN KEY (id_parcela) REFERENCES parcelas(id_parcela),
    FOREIGN KEY (id_clima) REFERENCES clima_diario(id_clima)
);

CREATE TABLE comentarios (
    id_comentario INT PRIMARY KEY IDENTITY(1,1),
    id_publicacion INT NOT NULL,
    id_usuario INT NOT NULL,
    texto NVARCHAR(MAX) NOT NULL,
    audio_ruta NVARCHAR(255) NULL,
    id_recomendacion INT NULL,  -- dato de campo de B.A.W.I. Riego adjunto (opcional)
    creado_en DATETIME DEFAULT GETDATE(),
    -- Nota: En SQL Server múltiples rutas de borrado en cascada (CASCADE) hacia usuarios pueden generar error.
    FOREIGN KEY (id_publicacion) REFERENCES publicaciones(id_publicacion) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario),
    FOREIGN KEY (id_recomendacion) REFERENCES recomendaciones_riego(id_recomendacion)
);

CREATE TABLE opciones (
    id_opcion INT PRIMARY KEY IDENTITY(1,1),
    id_pregunta INT NOT NULL,
    texto NVARCHAR(255) NOT NULL,
    es_correcta BIT DEFAULT 0,
    FOREIGN KEY (id_pregunta) REFERENCES preguntas(id_pregunta) ON DELETE CASCADE
);

CREATE TABLE intentos_quiz (
    id_intento INT PRIMARY KEY IDENTITY(1,1),
    id_usuario INT NOT NULL,
    id_quiz INT NOT NULL,
    aciertos TINYINT NOT NULL,
    total TINYINT NOT NULL,
    puntos_ganados INT NOT NULL,
    realizado_en DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario),
    FOREIGN KEY (id_quiz) REFERENCES quizzes(id_quiz)
);

-- Likes de publicaciones (no dan puntos; ordenan "Tendencias")
CREATE TABLE likes_publicacion (
    id_like INT PRIMARY KEY IDENTITY(1,1),
    id_publicacion INT NOT NULL,
    id_usuario INT NOT NULL,
    creado_en DATETIME DEFAULT GETDATE(),
    CONSTRAINT uq_like_publicacion UNIQUE (id_publicacion, id_usuario),
    FOREIGN KEY (id_publicacion) REFERENCES publicaciones(id_publicacion) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

CREATE TABLE votos_comentario (
    id_voto INT PRIMARY KEY IDENTITY(1,1),
    id_comentario INT NOT NULL,
    id_usuario INT NOT NULL,
    creado_en DATETIME DEFAULT GETDATE(),
    UNIQUE (id_comentario, id_usuario),
    FOREIGN KEY (id_comentario) REFERENCES comentarios(id_comentario) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

CREATE TABLE respuestas_usuario (
    id_respuesta INT PRIMARY KEY IDENTITY(1,1),
    id_intento INT NOT NULL,
    id_pregunta INT NOT NULL,
    id_opcion INT NOT NULL,
    es_correcta BIT NOT NULL,
    FOREIGN KEY (id_intento) REFERENCES intentos_quiz(id_intento) ON DELETE CASCADE,
    FOREIGN KEY (id_pregunta) REFERENCES preguntas(id_pregunta),
    FOREIGN KEY (id_opcion) REFERENCES opciones(id_opcion)
);
GO

-- ========================================================
-- 3. VISTAS PÚBLICAS
-- ========================================================
CREATE VIEW casos_publicos AS
SELECT 
    rr.id_recomendacion AS id_caso,
    rr.fecha,
    c.nombre AS cultivo,
    ec.nombre AS etapa,
    p.municipio,
    p.sistema,
    cd.temp_max_c,
    cd.humedad_rel_pct,
    cd.lluvia_mm,
    rr.et0_mm,
    rr.kc,
    rr.etc_mm,
    rr.factor_reposicion_pct,
    rr.horas_sugeridas,
    rr.horas_aplicadas,
    rr.estado,
    rr.motivo,
    rr.agua_ahorrada_m3
FROM recomendaciones_riego AS rr
INNER JOIN parcelas AS p ON rr.id_parcela = p.id_parcela
INNER JOIN usuarios AS u ON p.id_usuario = u.id_usuario
INNER JOIN cultivos AS c ON p.id_cultivo = c.id_cultivo
INNER JOIN etapas_cultivo AS ec ON p.id_etapa = ec.id_etapa
INNER JOIN clima_diario AS cd ON rr.id_clima = cd.id_clima
WHERE u.comparte_datos = 1
  AND rr.estado <> 'pendiente';
GO

-- ========================================================
-- 4. INSERCIÓN DE DATOS INICIALES (Adaptado de 02_seed.sql)
-- ========================================================

-- Catálogo de Rangos usando prefijo N para asegurar que los emojis se guarden correctamente
INSERT INTO rangos (id_rango, nombre, insignia, puntos_min, puntos_max, descripcion) VALUES
(1, N'Aprendiz del Campo', N'🌱', 0, 249, N'Rango inicial de Comunidad'),
(2, N'Técnico de Riego', N'💧', 250, 599, N'Rango intermedio de Comunidad'),
(3, N'Especialista Agrónomo', N'🌾', 600, 1199, N'Rango avanzado de Comunidad'),
(4, N'Maestro de la Tierra', N'👑', 1200, NULL, N'Rango máximo de Comunidad');

-- Catálogo de Cultivos con inserción directa sobre IDENTITY permitida o usando inserción simple si se omite el ID explícito.
-- Nota: Para insertar un valor explícito en una columna IDENTITY en SQL Server, es necesario activar IDENTITY_INSERT.
-- El orquestador (backend/services/orquestador.py) lee el Kc de estas tablas
SET IDENTITY_INSERT cultivos ON;
INSERT INTO cultivos (id_cultivo, clave, nombre, descripcion) VALUES
(1, N'nogal', N'Nogal pecanero', N'Cultivo de nogal pecanero'),
(2, N'manzana', N'Manzano', N'Cultivo de manzano');
SET IDENTITY_INSERT cultivos OFF;

INSERT INTO etapas_cultivo (id_cultivo, clave, nombre, kc, orden) VALUES
(1, N'inicial', N'Inicial', 0.40, 1),
(1, N'desarrollo', N'Desarrollo', 0.80, 2),
(1, N'media', N'Media (máximo consumo)', 1.15, 3),
(1, N'final', N'Final', 0.60, 4),
(2, N'inicial', N'Inicial', 0.30, 1),
(2, N'desarrollo', N'Desarrollo', 0.75, 2),
(2, N'media', N'Media (máximo consumo)', 1.00, 3),
(2, N'final', N'Final', 0.50, 4);

-- Tarifa 9-CU de CFE, octubre 2026
INSERT INTO tarifas_energia (nombre, precio_kwh, vigente_desde, fuente_url) VALUES
(N'9-CU', 0.7600, '2026-10-01',
 N'https://app.cfe.mx/Aplicaciones/CCFE/Tarifas/TarifasCRENegocio/Tarifas/AgricolaCargoUnico.aspx');
GO

-- ========================================================
-- 5. VERIFICACIÓN Y CONTEO RÁPIDO
-- ========================================================
-- Reemplazo de SHOW FULL TABLES;
SELECT name AS 'Nombre de Tabla' FROM sys.tables;

SELECT COUNT(*) AS total_rangos FROM rangos;
SELECT COUNT(*) AS total_cultivos FROM cultivos;
SELECT COUNT(*) AS total_etapas FROM etapas_cultivo;
SELECT COUNT(*) AS total_tarifas FROM tarifas_energia;
SELECT COUNT(*) AS total_usuarios FROM usuarios;
SELECT COUNT(*) AS total_parcelas FROM parcelas;
SELECT COUNT(*) AS total_clima FROM clima_diario;
SELECT COUNT(*) AS total_recomendaciones FROM recomendaciones_riego;
SELECT COUNT(*) AS total_quizzes FROM quizzes;
SELECT COUNT(*) AS total_preguntas FROM preguntas;
SELECT COUNT(*) AS total_opciones FROM opciones;
SELECT COUNT(*) AS total_intentos FROM intentos_quiz;
SELECT COUNT(*) AS total_respuestas FROM respuestas_usuario;
SELECT COUNT(*) AS total_publicaciones FROM publicaciones;
SELECT COUNT(*) AS total_comentarios FROM comentarios;
SELECT COUNT(*) AS total_votos FROM votos_comentario;
SELECT COUNT(*) AS total_movimientos_puntos FROM movimientos_puntos;
GO