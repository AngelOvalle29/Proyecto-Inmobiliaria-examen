"""Registro de los modelos de usuarios en el panel de Django.

Sin reglas de negocio.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Rol, Usuario


# Los formularios de Django están escritos para el User estándar, que tiene
# username. Solo se cambia el modelo y los campos; la validación de
# contraseñas sigue siendo la de Django.
class UsuarioCreacionForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ("email", "nombre_completo", "rol", "pais", "telefono")


class UsuarioEdicionForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = "__all__"


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = UsuarioEdicionForm
    add_form = UsuarioCreacionForm

    list_display = ["email", "nombre_completo", "rol", "is_active", "last_login"]
    list_filter = ["rol", "is_active", "is_staff"]
    search_fields = ["email", "nombre_completo"]
    ordering = ["email"]
    list_select_related = ["rol"]

    # Pantalla de edición. Reemplaza la de UserAdmin, que muestra username,
    # first_name y last_name.
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Datos personales", {"fields": ["nombre_completo", "telefono", "pais"]}),
        ("Acceso", {"fields": ["rol", "is_active", "is_staff", "is_superuser"]}),
        ("Permisos adicionales", {"fields": ["groups", "user_permissions"]}),
        ("Fechas", {"fields": ["last_login", "date_joined"]}),
    ]
    readonly_fields = ["last_login", "date_joined"]

    # Pantalla de alta.
    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": [
                    "email",
                    "nombre_completo",
                    "rol",
                    "pais",
                    "telefono",
                    "password1",
                    "password2",
                ],
            },
        ),
    ]

    # Los usuarios no se borran: se desactivan con is_active.
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    """
    Los roles los crea la migración y los define el enum NombreRol: desde el
    panel solo se edita la descripción.
    """

    list_display = ["nombre", "descripcion"]
    readonly_fields = ["nombre"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
