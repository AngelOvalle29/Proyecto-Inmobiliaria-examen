"""Vistas de catálogo: reciben la petición, delegan en un servicio o selector y
devuelven la respuesta.

Sin reglas de negocio ni consultas directas a los modelos.

Se usan las vistas genéricas de DRF, que ya validan, paginan y responden 404
o 400. Cada vista solo dice de qué selector salen los datos (get_queryset) y
qué servicio escribe (perform_create, perform_update, perform_destroy). En
vez de serializer.save(), que escribiría directo al modelo, cada perform_*
llama al servicio, que es quien aplica las reglas y audita.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveDestroyAPIView,
    RetrieveUpdateDestroyAPIView,
    get_object_or_404,
)
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.http import obtener_ip_cliente
from apps.usuarios.enums import NombreRol
from apps.usuarios.permissions import TieneRol

from .filters import DocumentoFilter, PropiedadFilter, UnidadFilter
from .models import Propiedad
from .selectors import (
    listar_avaluos,
    listar_documentos,
    listar_imagenes,
    listar_propiedades,
    listar_propiedades_con_portada,
    listar_tipos_propiedad,
    listar_unidades,
)
from .serializers import (
    AvaluoSerializer,
    CambiarEstadoSerializer,
    DescargaDocumentoSerializer,
    DocumentoOficialSerializer,
    DocumentoSubirSerializer,
    ImagenPropiedadSerializer,
    ImagenSubirSerializer,
    PropiedadSerializer,
    TipoPropiedadSerializer,
    UnidadSerializer,
)
from .services import (
    SEGUNDOS_URL_DESCARGA,
    actualizar_documento,
    actualizar_imagen,
    actualizar_propiedad,
    actualizar_tipo_propiedad,
    actualizar_unidad,
    cambiar_estado_propiedad,
    cambiar_estado_unidad,
    crear_propiedad,
    crear_tipo_propiedad,
    crear_unidad,
    desactivar_avaluo,
    desactivar_documento,
    desactivar_imagen,
    desactivar_propiedad,
    desactivar_tipo_propiedad,
    desactivar_unidad,
    generar_url_descarga,
    marcar_portada,
    registrar_avaluo,
    subir_documento,
    subir_imagen,
)

# Regla 8: leen todos los autenticados; escriben administración y gerencia.
# Los tipos de propiedad solo los cambia el administrador.
SOLO_ADMINISTRADOR = [NombreRol.ADMINISTRADOR]
ADMINISTRACION_Y_GERENCIA = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]

# Sin PUT: las ediciones son parciales (PATCH).
METODOS_DETALLE = ["get", "patch", "delete", "head", "options"]
# Un avalúo no se edita (regla 3): solo se consulta o se desactiva.
METODOS_AVALUO_DETALLE = ["get", "delete", "head", "options"]


# ---------- Tipos de propiedad ----------


class TiposPropiedadView(ListCreateAPIView):
    """GET y POST /api/v1/tipos-propiedad/"""

    serializer_class = TipoPropiedadSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": SOLO_ADMINISTRADOR}

    def get_queryset(self):
        return listar_tipos_propiedad()

    def perform_create(self, serializer):
        serializer.instance = crear_tipo_propiedad(
            datos=serializer.validated_data,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )


class TipoPropiedadDetalleView(RetrieveUpdateDestroyAPIView):
    """GET, PATCH y DELETE /api/v1/tipos-propiedad/{id}/"""

    serializer_class = TipoPropiedadSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {"PATCH": SOLO_ADMINISTRADOR, "DELETE": SOLO_ADMINISTRADOR}
    http_method_names = METODOS_DETALLE

    def get_queryset(self):
        return listar_tipos_propiedad()

    def perform_update(self, serializer):
        serializer.instance = actualizar_tipo_propiedad(
            tipo=serializer.instance,
            datos=serializer.validated_data,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )

    def perform_destroy(self, instance):
        desactivar_tipo_propiedad(
            tipo=instance, autor=self.request.user, ip=obtener_ip_cliente(self.request)
        )


# ---------- Propiedades ----------


class PropiedadesView(ListCreateAPIView):
    """GET y POST /api/v1/propiedades/ — con los filtros de PropiedadFilter."""

    serializer_class = PropiedadSerializer
    filterset_class = PropiedadFilter
    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ADMINISTRACION_Y_GERENCIA}

    def get_queryset(self):
        # Con la portada de cada fila en una sola consulta más (spec 019, §6).
        return listar_propiedades_con_portada()

    def perform_create(self, serializer):
        serializer.instance = crear_propiedad(
            datos=serializer.validated_data,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )


class PropiedadDetalleView(RetrieveUpdateDestroyAPIView):
    """GET, PATCH y DELETE /api/v1/propiedades/{id}/ — DELETE desactiva."""

    serializer_class = PropiedadSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {
        "PATCH": ADMINISTRACION_Y_GERENCIA,
        "DELETE": ADMINISTRACION_Y_GERENCIA,
    }
    http_method_names = METODOS_DETALLE

    def get_queryset(self):
        return listar_propiedades_con_portada()

    def perform_update(self, serializer):
        serializer.instance = actualizar_propiedad(
            propiedad=serializer.instance,
            datos=serializer.validated_data,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )

    def perform_destroy(self, instance):
        desactivar_propiedad(
            propiedad=instance,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )


class CambiarEstadoPropiedadView(GenericAPIView):
    """POST /api/v1/propiedades/{id}/cambiar-estado/"""

    serializer_class = CambiarEstadoSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ADMINISTRACION_Y_GERENCIA}

    def get_queryset(self):
        return listar_propiedades()

    @extend_schema(
        request=CambiarEstadoSerializer,
        responses={200: PropiedadSerializer},
        summary="Cambiar el estado de una propiedad",
    )
    def post(self, request: Request, pk: int) -> Response:
        propiedad = self.get_object()
        entrada = CambiarEstadoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        propiedad = cambiar_estado_propiedad(
            propiedad=propiedad,
            estado=entrada.validated_data["estado"],
            motivo=entrada.validated_data["motivo"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(PropiedadSerializer(propiedad).data)


# ---------- Unidades ----------


class UnidadesDePropiedadView(ListCreateAPIView):
    """GET y POST /api/v1/propiedades/{id}/unidades/?buscar= (código)"""

    serializer_class = UnidadSerializer
    filterset_class = UnidadFilter
    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ADMINISTRACION_Y_GERENCIA}

    def obtener_propiedad_de_la_url(self) -> Propiedad:
        """La propiedad del {id} de la ruta; 404 si no existe o está desactivada."""
        return get_object_or_404(listar_propiedades(), pk=self.kwargs["pk"])

    def get_queryset(self):
        # drf-spectacular llama a get_queryset sin una petición real para
        # documentar la vista, y entonces no hay {id} en la ruta.
        if getattr(self, "swagger_fake_view", False):
            return listar_unidades().none()
        return listar_unidades(propiedad=self.obtener_propiedad_de_la_url())

    def perform_create(self, serializer):
        serializer.instance = crear_unidad(
            propiedad=self.obtener_propiedad_de_la_url(),
            datos=serializer.validated_data,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )


class UnidadDetalleView(RetrieveUpdateDestroyAPIView):
    """GET, PATCH y DELETE /api/v1/unidades/{id}/ — DELETE desactiva."""

    serializer_class = UnidadSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {
        "PATCH": ADMINISTRACION_Y_GERENCIA,
        "DELETE": ADMINISTRACION_Y_GERENCIA,
    }
    http_method_names = METODOS_DETALLE

    def get_queryset(self):
        return listar_unidades()

    def perform_update(self, serializer):
        serializer.instance = actualizar_unidad(
            unidad=serializer.instance,
            datos=serializer.validated_data,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )

    def perform_destroy(self, instance):
        desactivar_unidad(
            unidad=instance,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )


class CambiarEstadoUnidadView(GenericAPIView):
    """POST /api/v1/unidades/{id}/cambiar-estado/"""

    serializer_class = CambiarEstadoSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ADMINISTRACION_Y_GERENCIA}

    def get_queryset(self):
        return listar_unidades()

    @extend_schema(
        request=CambiarEstadoSerializer,
        responses={200: UnidadSerializer},
        summary="Cambiar el estado de una unidad",
    )
    def post(self, request: Request, pk: int) -> Response:
        unidad = self.get_object()
        entrada = CambiarEstadoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        unidad = cambiar_estado_unidad(
            unidad=unidad,
            estado=entrada.validated_data["estado"],
            motivo=entrada.validated_data["motivo"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(UnidadSerializer(unidad).data)


# ---------- Avalúos ----------


class AvaluosDePropiedadView(ListCreateAPIView):
    """GET y POST /api/v1/propiedades/{id}/avaluos/ — el historial de plusvalía."""

    serializer_class = AvaluoSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ADMINISTRACION_Y_GERENCIA}

    def obtener_propiedad_de_la_url(self) -> Propiedad:
        """La propiedad del {id} de la ruta; 404 si no existe o está desactivada."""
        return get_object_or_404(listar_propiedades(), pk=self.kwargs["pk"])

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return listar_avaluos().none()
        return listar_avaluos(propiedad=self.obtener_propiedad_de_la_url())

    def perform_create(self, serializer):
        serializer.instance = registrar_avaluo(
            propiedad=self.obtener_propiedad_de_la_url(),
            datos=serializer.validated_data,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )


class AvaluoDetalleView(RetrieveDestroyAPIView):
    """GET y DELETE /api/v1/avaluos/{id}/ — DELETE desactiva (regla 3)."""

    serializer_class = AvaluoSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {"DELETE": ADMINISTRACION_Y_GERENCIA}
    http_method_names = METODOS_AVALUO_DETALLE

    def get_queryset(self):
        return listar_avaluos()

    def perform_destroy(self, instance):
        desactivar_avaluo(
            avaluo=instance,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )


# ---------- Documentos oficiales ----------


@extend_schema_view(
    post=extend_schema(
        request=DocumentoSubirSerializer,
        responses={201: DocumentoOficialSerializer},
    )
)
class DocumentosDePropiedadView(ListCreateAPIView):
    """GET y POST /api/v1/propiedades/{id}/documentos/ — POST multipart."""

    serializer_class = DocumentoOficialSerializer
    filterset_class = DocumentoFilter
    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ADMINISTRACION_Y_GERENCIA}

    def obtener_propiedad_de_la_url(self) -> Propiedad:
        """La propiedad del {id} de la ruta; 404 si no existe o está desactivada."""
        return get_object_or_404(listar_propiedades(), pk=self.kwargs["pk"])

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return listar_documentos().none()
        return listar_documentos(propiedad=self.obtener_propiedad_de_la_url())

    def create(self, request: Request, *args, **kwargs) -> Response:
        # La subida valida con DocumentoSubirSerializer y responde con los
        # datos del documento ya guardado, no con el archivo recibido.
        entrada = DocumentoSubirSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = dict(entrada.validated_data)
        archivo = datos.pop("archivo")

        documento = subir_documento(
            propiedad=self.obtener_propiedad_de_la_url(),
            archivo=archivo,
            datos=datos,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        salida = DocumentoOficialSerializer(
            documento, context=self.get_serializer_context()
        )
        return Response(salida.data, status=201)


class DocumentoDetalleView(RetrieveUpdateDestroyAPIView):
    """GET, PATCH y DELETE /api/v1/documentos/{id}/ — DELETE desactiva."""

    serializer_class = DocumentoOficialSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {
        "PATCH": ADMINISTRACION_Y_GERENCIA,
        "DELETE": ADMINISTRACION_Y_GERENCIA,
    }
    http_method_names = METODOS_DETALLE

    def get_queryset(self):
        return listar_documentos()

    def perform_update(self, serializer):
        serializer.instance = actualizar_documento(
            documento=serializer.instance,
            datos=serializer.validated_data,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )

    def perform_destroy(self, instance):
        desactivar_documento(
            documento=instance,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )


class DocumentoDescargaView(GenericAPIView):
    """GET /api/v1/documentos/{id}/descarga/ — URL firmada por 5 minutos."""

    serializer_class = DescargaDocumentoSerializer
    permission_classes = [TieneRol]

    def get_queryset(self):
        return listar_documentos()

    @extend_schema(
        responses={200: DescargaDocumentoSerializer},
        summary="Obtener la URL de descarga de un documento",
    )
    def get(self, request: Request, pk: int) -> Response:
        documento = self.get_object()
        url = generar_url_descarga(documento=documento)
        # En desarrollo el almacenamiento es local y devuelve /media/...: se
        # completa con el host de la API. La URL firmada de S3 ya es absoluta.
        if url.startswith("/"):
            url = request.build_absolute_uri(url)
        return Response({"url": url, "vence_en_segundos": SEGUNDOS_URL_DESCARGA})


# ---------- Imágenes de las propiedades (spec 019) ----------


@extend_schema_view(
    post=extend_schema(
        request=ImagenSubirSerializer,
        responses={201: ImagenPropiedadSerializer},
    )
)
class ImagenesDePropiedadView(ListCreateAPIView):
    """GET y POST /api/v1/propiedades/{id}/imagenes/ — POST multipart."""

    serializer_class = ImagenPropiedadSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ADMINISTRACION_Y_GERENCIA}

    def obtener_propiedad_de_la_url(self) -> Propiedad:
        """La propiedad del {id} de la ruta; 404 si no existe o está desactivada."""
        return get_object_or_404(listar_propiedades(), pk=self.kwargs["pk"])

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return listar_imagenes().none()
        return listar_imagenes(propiedad=self.obtener_propiedad_de_la_url())

    def create(self, request: Request, *args, **kwargs) -> Response:
        # Como los documentos: valida la entrada con ImagenSubirSerializer y
        # responde con la imagen ya guardada, con su URL firmada.
        entrada = ImagenSubirSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        imagen = subir_imagen(
            propiedad=self.obtener_propiedad_de_la_url(),
            archivo=entrada.validated_data["archivo"],
            descripcion=entrada.validated_data["descripcion"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        salida = ImagenPropiedadSerializer(
            imagen, context=self.get_serializer_context()
        )
        return Response(salida.data, status=201)


class ImagenDetalleView(RetrieveUpdateDestroyAPIView):
    """GET, PATCH y DELETE /api/v1/imagenes/{id}/ — DELETE desactiva."""

    serializer_class = ImagenPropiedadSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {
        "PATCH": ADMINISTRACION_Y_GERENCIA,
        "DELETE": ADMINISTRACION_Y_GERENCIA,
    }
    http_method_names = METODOS_DETALLE

    def get_queryset(self):
        return listar_imagenes()

    def perform_update(self, serializer):
        serializer.instance = actualizar_imagen(
            imagen=serializer.instance,
            datos=serializer.validated_data,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )

    def perform_destroy(self, instance):
        desactivar_imagen(
            imagen=instance,
            autor=self.request.user,
            ip=obtener_ip_cliente(self.request),
        )


class MarcarPortadaView(GenericAPIView):
    """POST /api/v1/imagenes/{id}/marcar-portada/ — sin cuerpo (regla 6)."""

    serializer_class = ImagenPropiedadSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ADMINISTRACION_Y_GERENCIA}

    def get_queryset(self):
        return listar_imagenes()

    @extend_schema(
        request=None,
        responses={200: ImagenPropiedadSerializer},
        summary="Marcar una imagen como la portada de su propiedad",
    )
    def post(self, request: Request, pk: int) -> Response:
        imagen = marcar_portada(
            imagen=self.get_object(),
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(self.get_serializer(imagen).data)
