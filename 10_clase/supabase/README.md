# Tabla `cuit_simulado` para Supabase

Una recomendación antes del SQL: usá `cuit_simulado` (guion bajo) en lugar de `cuit-simulado`. El guion obliga a entrecomillar el nombre en SQL. Si la creás con guion bajo, en el `.env` ponés `SUPABASE_TABLE=cuit_simulado`.

Decisiones de diseño:
- `cuit` es la clave primaria (texto de 11 dígitos), porque es lo que filtra la tool `consultar_cuit`.
- `actividad` y `errores` son `jsonb`, así PostgREST los devuelve ya como array, igual que tu response de ejemplo.
- Los textos van en UTF-8 correcto (`INFORMÁTICA`), sin el mojibake del ejemplo original.
- Los CUIT y las razones sociales son ficticios y no pasan la validación del dígito verificador, para no coincidir con contribuyentes reales. Los dos primeros coinciden con tu `datos.json`.

Pegalo completo en el **SQL Editor** de Supabase.

## 1. Crear la tabla

```sql
create table if not exists public.cuit_simulado (
    cuit                  text primary key check (cuit ~ '^\d{11}$'),
    error                 text  not null default 'N' check (error in ('N', 'S')),
    razon_social          text  not null,
    condicion_impositiva  text  not null,
    direccion             text,
    localidad             text,
    codigopostal          text,
    estado                text  not null default 'ACTIVO',
    provincia             text,
    actividad             jsonb not null default '[]'::jsonb,
    errores               jsonb not null default '[""]'::jsonb
);

-- Permitir lectura con la anon key (con la service_role key no hace falta)
alter table public.cuit_simulado enable row level security;

create policy "lectura publica cuit_simulado"
    on public.cuit_simulado for select
    using (true);
```

## 2. Insertar 20 registros

```sql
insert into public.cuit_simulado
    (cuit, razon_social, condicion_impositiva, direccion, localidad, codigopostal, estado, provincia, actividad)
values
('30712345678', 'TEXTILES NORPATAGONIA S.A.', 'RESPONSABLE INSCRIPTO', 'AV. ARGENTINA 1250', 'NEUQUEN', '8300', 'ACTIVO', 'NEUQUEN',
 '[{"descripcion":"ACABADO DE PRODUCTOS TEXTILES","id":"131300","nomenclador":"883","periodo":"201001"},
   {"descripcion":"SERVICIOS EMPRESARIALES N.C.P.","id":"829900","nomenclador":"883","periodo":"201906"}]'),

('20345567892', 'MODAS DEL SUR S.R.L.', 'RESPONSABLE INSCRIPTO', 'SAN MARTIN 480', 'BAHIA BLANCA', '8000', 'ACTIVO', 'BUENOS AIRES',
 '[{"descripcion":"CONFECCIÓN DE PRENDAS DE VESTIR, EXCEPTO PRENDAS DE PIEL Y DE CUERO","id":"141120","nomenclador":"883","periodo":"200901"}]'),

('30687654321', 'TEXTILES Y CONSULTORIA S.A.', 'RESPONSABLE INSCRIPTO', 'LA CALLE 123', 'CASTELAR', '1712', 'ACTIVO', 'BUENOS AIRES',
 '[{"descripcion":"SERVICIOS DE CONSULTORES EN INFORMÁTICA Y SUMINISTROS DE PROGRAMAS DE INFORMÁTICA","id":"620100","nomenclador":"883","periodo":"201311"},
   {"descripcion":"SERVICIOS EMPRESARIALES N.C.P.","id":"829900","nomenclador":"883","periodo":"201906"}]'),

('30709876543', 'HILANDERIA DEL PLATA S.A.', 'RESPONSABLE INSCRIPTO', 'CALLE 7 N 1020', 'LA PLATA', '1900', 'ACTIVO', 'BUENOS AIRES',
 '[{"descripcion":"ACABADO DE PRODUCTOS TEXTILES","id":"131300","nomenclador":"883","periodo":"200805"}]'),

('33711223344', 'COOPERATIVA TEXTIL LA UNION LTDA.', 'EXENTO', 'RUTA 9 KM 45', 'ROSARIO', '2000', 'ACTIVO', 'SANTA FE',
 '[{"descripcion":"CONFECCIÓN DE PRENDAS DE VESTIR, EXCEPTO PRENDAS DE PIEL Y DE CUERO","id":"141120","nomenclador":"883","periodo":"201203"}]'),

('30698877665', 'TRANSPORTES RIO DE LA PLATA S.R.L.', 'RESPONSABLE INSCRIPTO', 'AV. MITRE 3300', 'QUILMES', '1878', 'ACTIVO', 'BUENOS AIRES',
 '[{"descripcion":"SERVICIO DE TRANSPORTE AUTOMOTOR DE CARGAS","id":"494000","nomenclador":"883","periodo":"201201"}]'),

('30715432109', 'ESTUDIO CONTABLE FERNANDEZ Y ASOCIADOS S.R.L.', 'RESPONSABLE INSCRIPTO', 'AV. CORRIENTES 1450 PISO 3', 'CABA', '1042', 'ACTIVO', 'CAPITAL FEDERAL',
 '[{"descripcion":"SERVICIOS DE CONTABILIDAD, AUDITORÍA Y ASESORAMIENTO FISCAL","id":"692000","nomenclador":"883","periodo":"201505"}]'),

('30703216549', 'DENIM ANDINO S.A.', 'RESPONSABLE INSCRIPTO', 'ACCESO ESTE 2200', 'MENDOZA', '5500', 'ACTIVO', 'MENDOZA',
 '[{"descripcion":"ACABADO DE PRODUCTOS TEXTILES","id":"131300","nomenclador":"883","periodo":"201104"}]'),

('30711122233', 'SOFTWARE FACTORY ARGENTINA S.A.', 'RESPONSABLE INSCRIPTO', 'BV. SAN JUAN 650', 'CORDOBA', '5000', 'ACTIVO', 'CORDOBA',
 '[{"descripcion":"SERVICIOS DE CONSULTORES EN INFORMÁTICA Y SUMINISTROS DE PROGRAMAS DE INFORMÁTICA","id":"620100","nomenclador":"883","periodo":"201507"}]'),

('30694455667', 'INMOBILIARIA DEL OESTE S.A.', 'RESPONSABLE INSCRIPTO', 'AV. RIVADAVIA 17500', 'MORON', '1708', 'ACTIVO', 'BUENOS AIRES',
 '[{"descripcion":"SERVICIOS INMOBILIARIOS REALIZADOS POR CUENTA PROPIA, CON BIENES URBANOS PROPIOS O ARRENDADOS N.C.P.","id":"681098","nomenclador":"883","periodo":"201402"}]'),

('30708899001', 'GASTRONOMIA PATAGONICA S.R.L.', 'RESPONSABLE INSCRIPTO', 'AV. FONTANA 340', 'TRELEW', '9100', 'ACTIVO', 'CHUBUT',
 '[{"descripcion":"SERVICIOS DE EXPENDIO DE COMIDAS Y BEBIDAS EN RESTAURANTES Y CANTINAS SIN ESPECTÁCULO","id":"561010","nomenclador":"883","periodo":"201108"}]'),

('30716677889', 'CONFECCIONES TUCUMAN S.A.', 'RESPONSABLE INSCRIPTO', 'AV. MATE DE LUNA 2100', 'SAN MIGUEL DE TUCUMAN', '4000', 'ACTIVO', 'TUCUMAN',
 '[{"descripcion":"CONFECCIÓN DE PRENDAS DE VESTIR, EXCEPTO PRENDAS DE PIEL Y DE CUERO","id":"141120","nomenclador":"883","periodo":"201006"}]'),

('30701234987', 'LOGISTICA RAMOS S.R.L.', 'RESPONSABLE INSCRIPTO', 'AV. DE MAYO 650', 'RAMOS MEJIA', '1704', 'ACTIVO', 'BUENOS AIRES',
 '[{"descripcion":"SERVICIO DE TRANSPORTE AUTOMOTOR DE CARGAS","id":"494000","nomenclador":"883","periodo":"201309"},
   {"descripcion":"SERVICIOS EMPRESARIALES N.C.P.","id":"829900","nomenclador":"883","periodo":"201906"}]'),

('30713344556', 'TEJIDOS DEL LITORAL S.A.', 'RESPONSABLE INSCRIPTO', 'CALLE URQUIZA 780', 'PARANA', '3100', 'ACTIVO', 'ENTRE RIOS',
 '[{"descripcion":"ACABADO DE PRODUCTOS TEXTILES","id":"131300","nomenclador":"883","periodo":"200912"}]'),

('30699988776', 'SERVICIOS INFORMATICOS SAN JUSTO S.R.L.', 'RESPONSABLE INSCRIPTO', 'AV. ARIEGO 2300', 'SAN JUSTO', '1754', 'ACTIVO', 'BUENOS AIRES',
 '[{"descripcion":"SERVICIOS DE CONSULTORES EN INFORMÁTICA Y SUMINISTROS DE PROGRAMAS DE INFORMÁTICA","id":"620100","nomenclador":"883","periodo":"201610"}]'),

('27298765431', 'GOMEZ LAURA BEATRIZ', 'MONOTRIBUTO', 'BELGRANO 55', 'TIGRE', '1648', 'ACTIVO', 'BUENOS AIRES',
 '[{"descripcion":"CONFECCIÓN DE PRENDAS DE VESTIR, EXCEPTO PRENDAS DE PIEL Y DE CUERO","id":"141120","nomenclador":"883","periodo":"201807"}]'),

('20312345679', 'PEREZ JUAN CARLOS', 'MONOTRIBUTO', 'ESPAÑA 1220', 'MAR DEL PLATA', '7600', 'ACTIVO', 'BUENOS AIRES',
 '[{"descripcion":"SERVICIO DE TRANSPORTE AUTOMOTOR DE CARGAS","id":"494000","nomenclador":"883","periodo":"201703"}]'),

('30705566778', 'ESTAMPERIA NORTE S.A.', 'RESPONSABLE INSCRIPTO', 'RUTA 34 KM 12', 'SALTA', '4400', 'INACTIVO', 'SALTA',
 '[{"descripcion":"ACABADO DE PRODUCTOS TEXTILES","id":"131300","nomenclador":"883","periodo":"201101"}]'),

('30710011223', 'ASESORES IMPOSITIVOS DEL SUR S.R.L.', 'RESPONSABLE INSCRIPTO', 'AV. HIPOLITO YRIGOYEN 8900', 'LOMAS DE ZAMORA', '1832', 'ACTIVO', 'BUENOS AIRES',
 '[{"descripcion":"SERVICIOS DE CONTABILIDAD, AUDITORÍA Y ASESORAMIENTO FISCAL","id":"692000","nomenclador":"883","periodo":"201211"},
   {"descripcion":"SERVICIOS EMPRESARIALES N.C.P.","id":"829900","nomenclador":"883","periodo":"201906"}]'),

('30714433221', 'FIBRAS Y COLORES S.A.', 'RESPONSABLE INSCRIPTO', 'AV. DEL LIBERTADOR 14500', 'SAN ISIDRO', '1642', 'ACTIVO', 'BUENOS AIRES',
 '[{"descripcion":"ACABADO DE PRODUCTOS TEXTILES","id":"131300","nomenclador":"883","periodo":"201309"},
   {"descripcion":"CONFECCIÓN DE PRENDAS DE VESTIR, EXCEPTO PRENDAS DE PIEL Y DE CUERO","id":"141120","nomenclador":"883","periodo":"201309"}]');
```

Son 19 filas más una última abajo (para llegar a 20), con un caso `INACTIVO` y dos `MONOTRIBUTO` para probar variantes:

```sql
insert into public.cuit_simulado
    (cuit, razon_social, condicion_impositiva, direccion, localidad, codigopostal, estado, provincia, actividad)
values
('30702233445', 'MODAS PALERMO S.A.', 'RESPONSABLE INSCRIPTO', 'THAMES 1650', 'CABA', '1425', 'ACTIVO', 'CAPITAL FEDERAL',
 '[{"descripcion":"CONFECCIÓN DE PRENDAS DE VESTIR, EXCEPTO PRENDAS DE PIEL Y DE CUERO","id":"141120","nomenclador":"883","periodo":"201504"}]');
```

## 3. Verificar

```sql
select count(*) from public.cuit_simulado;                     -- 20
select * from public.cuit_simulado where cuit = '30687654321';  -- el CUIT del ejemplo de Castelar
```

## 4. Probar desde la API REST (lo mismo que hace tu tool)

```bash
curl "https://TU_PROYECTO.supabase.co/rest/v1/cuit_simulado?cuit=eq.30687654321&limit=1" \
  -H "apikey: TU_KEY" -H "Authorization: Bearer TU_KEY"
```

Devuelve una lista con un objeto que incluye `cuit` además de los campos de tu response original. Si querés exactamente el mismo shape, agregá `&select=error,razon_social,condicion_impositiva,direccion,localidad,codigopostal,estado,provincia,actividad,errores` a la URL, o ponelo en el `params` de `consultar_cuit` en `tools.py`.

Con esta tabla ya podés usar el filtro `cuit=eq.<valor>` del código anterior, así que cada CUIT devuelve su propio registro en lugar de una fila fija.
