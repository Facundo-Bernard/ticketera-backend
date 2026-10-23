import logging
from .model import User
from .security import hash_password
from ...config.settings import settings

logger = logging.getLogger(__name__)

async def seed_default_admin():
    """
    Verifica si existe el usuario administrador maestro configurado en settings.
    - Si no existe: lo crea automáticamente con la contraseña inicial de .env y rol 'admin'.
    - Si ya existe: respeta la contraseña existente (nunca la sobreescribe) y asegura que esté activo y con rol 'admin'.
    """
    admin_email = settings.MASTER_ADMIN_EMAIL.strip().lower()
    admin_password = settings.MASTER_ADMIN_PASSWORD

    existing_admin = await User.find_one(User.email == admin_email)
    if not existing_admin:
        if not admin_password:
            logger.warning(f"No se configuró MASTER_ADMIN_PASSWORD en .env. No se pudo crear el usuario {admin_email}.")
            return

        admin_user = User(
            email=admin_email,
            nombre="Administrador General",
            hashed_password=hash_password(admin_password),
            rol="admin",
            activo=True
        )
        await admin_user.insert()
        logger.info(f"Cuenta de administrador maestro creada exitosamente: {admin_email}")
    else:
        # Si la cuenta ya existe en la base de datos persistente, preservamos la contraseña existente
        # para que cualquier cambio de contraseña previo no sea sobreescrito en cada reinicio.
        needs_save = False
        if not existing_admin.activo:
            existing_admin.activo = True
            needs_save = True
        if existing_admin.rol != "admin":
            existing_admin.rol = "admin"
            needs_save = True

        if needs_save:
            await existing_admin.save()
            logger.info(f"Cuenta de administrador maestro activada/sincronizada sin modificar contraseña: {admin_email}")
        else:
            logger.info(f"Cuenta de administrador maestro ya existente y activa: {admin_email}")
