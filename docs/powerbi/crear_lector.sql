-- Rol de solo lectura para Power BI (spec 021, §4).
--
-- Se corre una vez, a mano, en el SQL Editor de Neon, con el usuario dueño de
-- la base. neondb es el nombre que Neon da por defecto: si DATABASE_URL de
-- Render termina en otro nombre, cámbielo en el GRANT CONNECT.
--
-- Antes de correrlo, cambie CLAVE_AQUI por una contraseña fuerte, y no guarde
-- el archivo con ella: la contraseña nunca va
-- al repositorio, a un issue, a un PR ni a una captura. Pásela por privado.
--
-- Se crea con SQL y no desde la consola de Neon a propósito: los roles de la
-- consola entran a neon_superuser, con permisos amplios. Este nace sin ninguno
-- y solo recibe lectura de las cuatro vistas del esquema bi.

CREATE ROLE powerbi_reader WITH LOGIN PASSWORD 'CLAVE_AQUI';

-- Solo conectarse y leer las vistas. Sin permisos de escritura, sin lectura de
-- las tablas del sistema y sin privilegios por defecto sobre objetos futuros:
-- una vista nueva se le concede de forma explícita.
GRANT CONNECT ON DATABASE neondb TO powerbi_reader;
GRANT USAGE ON SCHEMA bi TO powerbi_reader;
GRANT SELECT ON bi.dim_tiempo, bi.dim_geografia, bi.dim_propiedad, bi.hechos_ventas
    TO powerbi_reader;
REVOKE ALL ON SCHEMA public FROM powerbi_reader;

-- Comprobación (spec 021: "una consulta de tabla operativa debe fallar").
-- Conéctese como powerbi_reader y corra:
--   SELECT COUNT(*) FROM bi.hechos_ventas;       -- funciona
--   SELECT COUNT(*) FROM ventas_contratoventa;   -- debe responder "permission denied"
