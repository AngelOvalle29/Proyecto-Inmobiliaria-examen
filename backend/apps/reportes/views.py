"""HTTP de catálogo, vista previa y descargas autenticadas (spec 016)."""

import json
from dataclasses import asdict

from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404, HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param

from .catalogo import definicion_reporte
from .exportadores import exportar_excel, exportar_pdf
from .selectors import listar_reportes
from .serializers import FILTROS, CatalogoReporteSerializer, ReporteSerializer
from .services import (
    comprobar_permiso,
    obtener_reporte_exportacion,
    obtener_reporte_paginado,
)


class CatalogoReportesView(GenericAPIView):
    queryset = []
    filter_backends = []
    serializer_class = CatalogoReporteSerializer
    pagination_class = PageNumberPagination

    @extend_schema(responses=CatalogoReporteSerializer(many=True))
    def get(self, request):
        pagina = self.paginate_queryset(listar_reportes(usuario=request.user))
        return self.get_paginated_response(self.get_serializer(pagina, many=True).data)


# El slug decide qué subconjunto de parámetros se admite. El esquema documenta
# todos, y los metadatos indican cuáles construir para cada reporte.
PARAMETROS = [
    OpenApiParameter(n, t, description=e)
    for n, t, e in [
        ("pais", int, "R05/R16: ID del país"),
        ("ciudad", int, "R05: ID de ciudad"),
        ("tipo", str, "R05: ID de tipo; R16: código de documento"),
        ("moneda", str, "R05: código ISO de moneda"),
        *[
            (n, str, "R05: decimal inclusivo")
            for n in ("precio_min", "precio_max", "area_min", "area_max")
        ],
        ("dias_anticipacion", int, "R16: 0 a 365, por defecto 30"),
        ("usuario", int, "R17: ID del usuario"),
        ("entidad", str, "R17: entidad exacta"),
        ("accion", str, "R17: acción de auditoría"),
        ("fecha_desde", str, "Día ISO de Guatemala, inclusivo"),
        ("fecha_hasta", str, "Día ISO de Guatemala, inclusivo"),
        ("agente", int, "R01/R02/R03/R10/R11: ID del agente"),
        ("cliente", int, "R10: ID del cliente"),
        ("modalidad", str, "R01: CONTADO o FINANCIADO"),
        ("origen", str, "R12: CONTADO, ENGANCHE, CUOTA o RENTA"),
        ("estado", str, "R03/R10: estado"),
        *[
            (n, str, "R03/R11: decimal inclusivo; exige moneda")
            for n in ("monto_min", "monto_max", "saldo_min", "saldo_max")
        ],
    ]
]


class ReporteView(GenericAPIView):
    serializer_class = ReporteSerializer

    @extend_schema(
        parameters=[*PARAMETROS, OpenApiParameter("page", int)],
        responses=ReporteSerializer,
    )
    def get(self, request, slug):
        comprobar_permiso(slug=slug, usuario=request.user)
        parametros = request.query_params.copy()
        pagina = parametros.pop("page", ["1"])
        try:
            if len(pagina) != 1 or not pagina[0].isdigit():
                raise ValueError
            numero = int(pagina[0])
        except ValueError as exc:
            raise Http404 from exc
        clase, estructura = FILTROS[slug]
        entrada = clase(data=parametros)
        entrada.is_valid(raise_exception=True)
        resultado = obtener_reporte_paginado(
            slug=slug,
            filtros=estructura(**entrada.validated_data),
            usuario=request.user,
            pagina=numero,
        )
        datos = asdict(resultado.reporte)
        enlace = request.build_absolute_uri()
        datos["filas"] = dict(
            count=resultado.count,
            next=replace_query_param(enlace, "page", numero + 1)
            if numero * 25 < resultado.count
            else None,
            previous=replace_query_param(enlace, "page", numero - 1)
            if numero > 1
            else None,
            results=datos["filas"],
        )
        # Conserva Decimal como texto decimal exacto, igual que los campos
        # monetarios del resto de la API; evita convertirlos a float en JSON.
        datos = json.loads(json.dumps(datos, cls=DjangoJSONEncoder))
        return Response(self.get_serializer(datos).data)


class ExportarReporteView(GenericAPIView):
    formato = "excel"
    serializer_class = ReporteSerializer

    @extend_schema(
        parameters=PARAMETROS,
        responses={(200, "application/octet-stream"): OpenApiResponse(bytes)},
    )
    def get(self, request, slug):
        comprobar_permiso(slug=slug, usuario=request.user)
        clase, estructura = FILTROS[slug]
        entrada = clase(data=request.query_params)
        entrada.is_valid(raise_exception=True)
        reporte = obtener_reporte_exportacion(
            slug=slug,
            filtros=estructura(**entrada.validated_data),
            usuario=request.user,
        )
        excel = self.formato == "excel"
        extension = "xlsx" if excel else "pdf"
        contenido = exportar_excel(reporte) if excel else exportar_pdf(reporte)
        tipo = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if excel
            else "application/pdf"
        )
        respuesta = HttpResponse(contenido, content_type=tipo)
        codigo = definicion_reporte(slug)["codigo"]
        fecha = timezone.localdate(reporte.generado_en)
        nombre = f"{codigo}_{slug.replace('-', '_')}_{fecha:%Y-%m-%d}.{extension}"
        respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
        respuesta["Cache-Control"] = "private, no-store"
        return respuesta
