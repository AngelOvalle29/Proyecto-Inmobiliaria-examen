"""Modelos de auditoría: campos, relaciones, constraints y validación propia.

No llaman a servicios ni envían correos.
"""

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from .enums import AccionAuditoria
from .exceptions import RegistroAuditoriaInmutable


class LogAuditoria(models.Model):
    """
    Una operación de escritura sobre una entidad del sistema
    (docs/arquitectura.md §5). Lo crea registrar_auditoria y nada más.

    Es de solo inserción: un registro de auditoría que se puede editar no
    sirve como evidencia. save() y delete() lo impiden para cualquier código
    que pase por el modelo; QuerySet.update() y QuerySet.delete() sí lo
    saltan, así que ningún código del proyecto debe usarlos sobre esta tabla.
    """

    # Referencia por settings.AUTH_USER_MODEL y no importando Usuario:
    # auditoria no importa ninguna app (spec 001, §4).
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="registros_auditoria",
    )
    # Nombre de la tabla afectada, por ejemplo "usuarios_usuario".
    entidad = models.CharField(max_length=100)
    # Nulo cuando no hay registro asociado, como en un login fallido con un
    # correo que no existe.
    entidad_id = models.BigIntegerField(null=True, blank=True)
    accion = models.CharField(max_length=20, choices=AccionAuditoria.choices)
    # DjangoJSONEncoder porque los valores incluyen montos (Decimal) y fechas,
    # que el codificador JSON estándar de Python no sabe escribir.
    valores_anteriores = models.JSONField(
        null=True, blank=True, encoder=DjangoJSONEncoder
    )
    valores_nuevos = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    # auto_now_add: la fecha la pone la base al insertar; nadie puede
    # registrar una operación con otra fecha.
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auditoria_log_sistema"
        ordering = ["-fecha"]
        verbose_name = "registro de auditoría"
        verbose_name_plural = "registros de auditoría"
        indexes = [
            # "Historia de este contrato": todas las operaciones de un registro.
            models.Index(
                fields=["entidad", "entidad_id"], name="auditoria_entidad_idx"
            ),
            # Consultas y reportes por rango de fechas.
            models.Index(fields=["fecha"], name="auditoria_fecha_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_accion_display()} {self.entidad} #{self.entidad_id}"

    def save(self, *args, **kwargs):
        # _state.adding es True solo mientras el objeto aún no existe en la
        # base. Si es False, alguien intenta modificar un registro guardado.
        if not self._state.adding:
            raise RegistroAuditoriaInmutable(
                "Los registros de auditoría no se modifican."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroAuditoriaInmutable("Los registros de auditoría no se borran.")
