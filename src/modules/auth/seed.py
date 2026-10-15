import logging
from .model import User
from .security import hash_password
from ...config.settings import settings

logger = logging.getLogger(__name__)

async def seed_default_admin():
    """
    Verifica si existe el usuario administrador maestro configurado en settings.
    Si no existe, lo crea automáticamente con la contraseña y rol 'admin'.
    Si ya existe, sincroniza la contraseña y asegura que esté activo.
    """
    admin_email = settings.MASTER_ADMIN_EMAIL.strip().lower()
    admin_password = settings.MASTER_ADMIN_PASSWORD

    existing_admin = await User.find_one(User.email == admin_email)
    if not existing_admin:
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
        # Aseguramos que la cuenta esté activa, con rol admin y sincronizada
        existing_admin.activo = True
        existing_admin.rol = "admin"
        existing_admin.hashed_password = hash_password(admin_password)
        await existing_admin.save()
        logger.info(f"Cuenta de administrador maestro sincronizada: {admin_email}")
