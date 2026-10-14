"""Modelos de usuarios: campos, relaciones, constraints y validación propia.

No llaman a servicios ni envían correos.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower

from .enums import NombreRol


class Rol(models.Model):
    """
    Rol de un usuario. Es una tabla y no un campo de texto para poder
    asociarle permisos más adelante sin migrar datos (spec 001, §10).

    Los cinco roles los crea la migración 0002; no se agregan a mano.
    """

    nombre = models.CharField(max_length=20, unique=True, choices=NombreRol.choices)
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "rol"
        verbose_name_plural = "roles"

    def __str__(self) -> str:
        return self.get_nombre_display()


class UsuarioManager(BaseUserManager):
    """
    Crea usuarios identificados por correo en lugar de nombre de usuario.

    Django exige un manager propio cuando el modelo no tiene username: el
    comando createsuperuser y el panel llaman a estos métodos. Por eso la
    regla 3 vive aquí y no en un servicio: createsuperuser no pasa por
    services.py.
    """

    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        """
        Correo completo en minúsculas (regla 1). Django solo baja el dominio,
        así que Ana@demo.test y ana@demo.test serían dos cuentas. Este método
        lo usan el manager, el formulario del panel (AbstractUser.clean) y el
        selector de logins fallidos, así que todos guardan y buscan igual.
        """
        return super().normalize_email(email).lower()

    def get_by_natural_key(self, email):
        """
        Lo usa authenticate() en el login. Sin distinguir mayúsculas, para que
        también encuentre cuentas guardadas antes de normalizar el correo.
        """
        return self.get(email__iexact=email)

    def _crear_usuario(self, email, password, **campos):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")
        if campos.get("rol") is None:
            raise ValueError("Todo usuario debe tener un rol (regla 2).")
        email = self.normalize_email(email)
        usuario = self.model(email=email, **campos)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **campos):
        campos.setdefault("is_staff", False)
        campos.setdefault("is_superuser", False)
        return self._crear_usuario(email, password, **campos)

    def create_superuser(self, email, password=None, **campos):
        """Regla 3: todo superusuario tiene el rol ADMINISTRADOR, siempre."""
        campos["is_staff"] = True
        campos["is_superuser"] = True
        campos["rol"] = Rol.objects.get(nombre=NombreRol.ADMINISTRADOR)
        return self._crear_usuario(email, password, **campos)


class Usuario(AbstractUser):
    """
    Usuario del sistema. Inicia sesión con su correo (regla 1).

    Se reutilizan dos campos de AbstractUser en lugar de duplicarlos:
    last_login es el último acceso e is_active es el borrado lógico. Django
    ya impide autenticarse a un usuario con is_active en False.
    """

    # Asignar None elimina el campo heredado de AbstractUser.
    username = None
    first_name = None
    last_name = None

    email = models.EmailField("correo electrónico", unique=True)
    nombre_completo = models.CharField(max_length=150)
    # PROTECT: un rol con usuarios asignados no se puede borrar (regla 2).
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="usuarios")
    pais = models.ForeignKey(
        "core.Pais",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="usuarios",
    )
    telefono = models.CharField(max_length=30, blank=True)

    USERNAME_FIELD = "email"
    # Lo que createsuperuser pide además del correo y la contraseña. El rol no
    # se pide porque create_superuser lo asigna.
    REQUIRED_FIELDS = ["nombre_completo"]

    objects = UsuarioManager()

    class Meta:
        ordering = ["email"]
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            # Regla 1: un correo, una cuenta, sin importar mayúsculas. unique=True
            # en el campo no basta, porque distingue Ana@ de ana@.
            models.UniqueConstraint(
                Lower("email"), name="usuarios_usuario_email_unico_sin_mayusculas"
            ),
        ]

    def __str__(self) -> str:
        return self.email

    # AbstractUser arma estos dos a partir de first_name y last_name, que aquí
    # no existen.
    def get_full_name(self) -> str:
        return self.nombre_completo

    def get_short_name(self) -> str:
        return self.nombre_completo
