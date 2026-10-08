# B.A.W.Í. — Agua, talento y comunidad

Ecosistema para productores agrícolas de Chihuahua:

- **B.A.W.Í. Riego**: recomendación diaria de riego con el clima real de la parcela,
  FAO-56 Penman-Monteith, lógica difusa y el ahorro de agua, energía y dinero.
- **B.A.W.Í. Comunidad**: foro entre productores con rangos, puntos y capacitación.

| Parte | Tecnología | Puerto |
|---|---|---|
| API (backend) | FastAPI + SQLAlchemy | 8000 |
| App Riego | Streamlit | 8502 |
| App Comunidad | Streamlit | 8503 |
| Base de datos | SQL Server Express | — |

## Cómo calcula B.A.W.Í. Riego

1. **Clima real** de la parcela con [Open-Meteo](https://open-meteo.com) (gratuito, sin clave):
   temperatura máxima y mínima, humedad relativa máxima y mínima, viento, radiación solar,
   altitud y el pronóstico de lluvia de las próximas 24 h. Se usa la latitud y longitud de la
   parcela si están guardadas; si no, la de la cabecera municipal (Delicias, Cuauhtémoc, Camargo
   o Chihuahua).
2. **ET₀** diaria con FAO-56 Penman-Monteith (`backend/services/fao56_calc.py`).
3. **ETc = ET₀ × Kc**, con el Kc de la etapa del cultivo de la tabla `etapas_cultivo`.
4. **Lógica difusa** (`backend/services/motor_difuso.py`): riesgo de estrés hídrico y porcentaje
   del déficit a reponer según la probabilidad de lluvia.
5. **Horas de riego** = lámina ÷ tasa de aplicación del sistema.
6. **Ahorro** contra el riego habitual, con el precio vigente de la Tarifa 9-CU de la tabla
   `tarifas_energia`.

## Requisitos

- Windows con **Python 3.13**
- **SQL Server Express** (instancia `localhost\SQLEXPRESS`) y **ODBC Driver 18 for SQL Server**
- Conexión a internet (para el clima)

## Instalación (una sola vez)

En PowerShell, desde la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env`:

- `SECRET_KEY`: genera una con `python -c "import secrets; print(secrets.token_hex(32))"`
- `DB_SERVER`, `DB_USER`, `DB_PASSWORD` si tu SQL Server es distinto
- `SMTP_USER` y `SMTP_PASSWORD` para enviar el código al crear cuentas en Comunidad
  (con Gmail, una *contraseña de aplicación*). Sin estos datos no se pueden crear cuentas nuevas.

Crea la base de datos y carga el contenido de Capacitación:

```powershell
sqlcmd -S localhost\SQLEXPRESS -E -C -f 65001 -i database\bawi_database.sql
python -m backend.seed_capacitacion
python -m backend.seed_formularios
python -m backend.seed_formularios --aprobar
```

> `bawi_database.sql` **borra y vuelve a crear** la base `bawi`. Solo úsalo en una instalación nueva.

Registra la parcela del productor (debe tener cuenta en Comunidad) y pon el id que muestra
en `.env` como `RIEGO_ID_PARCELA`:

```powershell
python -m backend.registrar_parcela --usuario productor@correo.com --nombre "Huerta El Nogalito" --municipio Delicias --cultivo nogal --etapa media --area 10 --sistema goteo --tasa 3 --bomba-kw 45 --horas-habituales 4
```

Para comprobar la conexión a la base: `python -m backend.db`

## Ejecutar

Abre **tres** terminales en la carpeta del proyecto y en cada una activa el entorno
(`.\.venv\Scripts\Activate.ps1`):

```powershell
# Terminal 1 - API
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Terminal 2 - B.A.W.I. Riego
streamlit run apps/riego/app.py --server.port 8502

# Terminal 3 - B.A.W.I. Comunidad
streamlit run apps/comunidad/app.py --server.port 8503
```

**Con Git Bash** (por ejemplo, en la terminal de VS Code) el entorno se activa así:

```bash
source .venv/Scripts/activate
```

y los tres comandos son los mismos.

- Riego: <http://localhost:8502>
- Comunidad: <http://localhost:8503>
- Documentación de la API: <http://localhost:8000/docs>

## Estructura

```
apps/riego/app.py            App de Riego (Streamlit)
apps/comunidad/app.py        App de Comunidad (Streamlit)
backend/main.py              API (FastAPI): diagnóstico de riego, parcela, decisión e historial
backend/routers/             Rutas de Comunidad y Capacitación
backend/services/            Clima, FAO-56, lógica difusa, ahorro, catálogos, cuentas, correo, puntos
backend/registrar_parcela.py Alta de la parcela de un productor
backend/seed_*.py            Carga del contenido de Capacitación
database/bawi_database.sql   Esquema completo de la base de datos
database/formularios.json    Formularios de Capacitación
```
