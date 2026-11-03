-- Ejecutar con powerbi_reader. No contiene credenciales ni escrituras.
SELECT COUNT(*) AS contratos, COALESCE(SUM(neto_usd), 0) AS ventas_usd
FROM bi.hechos_ventas;

SELECT t.anio_mes, g.pais, p.tipo, COUNT(*) AS contratos,
       SUM(v.neto_usd) AS ventas_usd
FROM bi.hechos_ventas v
JOIN bi.dim_tiempo t ON t.fecha_id = v.fecha_id
JOIN bi.dim_geografia g ON g.ciudad_id = v.ciudad_id
JOIN bi.dim_propiedad p ON p.bien_clave = v.bien_clave
GROUP BY t.anio_mes, g.pais, p.tipo
ORDER BY t.anio_mes, g.pais, p.tipo;

-- Debe dar cero: ninguna venta queda sin dimensión.
SELECT COUNT(*) AS ventas_sin_dimension
FROM bi.hechos_ventas v
LEFT JOIN bi.dim_tiempo t ON t.fecha_id = v.fecha_id
LEFT JOIN bi.dim_geografia g ON g.ciudad_id = v.ciudad_id
LEFT JOIN bi.dim_propiedad p ON p.bien_clave = v.bien_clave
WHERE t.fecha_id IS NULL OR g.ciudad_id IS NULL OR p.bien_clave IS NULL;
