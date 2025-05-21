from handlers.admin import register_admin_handlers
from handlers.user import register_user_handlers
from handlers.payment import register_payment_handlers


def register_all_handlers(dp):
    """
    Регистрация всех обработчиков
    """
    handlers = (
        register_admin_handlers,
        register_user_handlers,
        register_payment_handlers,
    )
    
    for handler in handlers:
        handler(dp)
