import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture(autouse=True)
def silence_push_notifications_in_tests():
    """
    Silencia el envío de notificaciones Web Push reales durante la ejecución de los tests
    para no saturar el navegador ni el sistema operativo con alertas de escritorio.
    """
    with patch("src.modules.notifications.service.NotificationService.broadcast", new_callable=AsyncMock) as mock_broadcast:
        mock_broadcast.return_value = 0
        yield mock_broadcast
