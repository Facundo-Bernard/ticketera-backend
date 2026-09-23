import logging
from .model import User
from .security import hash_password

logger = logging.getLogger(__name__)

async def seed_default_admin():
    """
    Verifica si existe el usuario administrador genérico 'admin@coopya.com'.
    Si no existe, lo crea automáticamente con contraseña 'admin' y rol 'admin'.
    """
    admin_email = "admin@coopya.com"
    existing_admin = await User.find_one(User.email == admin_email)
    if not existing_admin:
        admin_user = User(
            email=admin_email,
            nombre="Administrador General",
            hashed_password=hash_password("admin"),
            rol="admin",
            activo=True
        )
        await admin_user.insert()
        logger.info(f"Usuario genérico creado exitosamente: {admin_email}")
    else:
        # Aseguramos que la cuenta esté activa
        if not existing_admin.activo:
            existing_admin.activo = True
            await existing_admin.save()
