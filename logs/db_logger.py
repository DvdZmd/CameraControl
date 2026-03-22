import traceback
from database.models import ErrorLog, db
from flask import has_app_context

def log_error_to_db(module, exception):
    """
    Persist an exception record to the application database.

    The function requires an active Flask application context because it writes
    through the configured SQLAlchemy session. When no application context is
    available, the call is ignored to avoid secondary failures during error
    handling.

    Args:
        module: Logical source of the error being recorded.
        exception: Exception instance to serialize into the log entry.

    Returns:
        None
    """
    if not has_app_context():
        return  # prevenimos errores si se llama sin contexto de Flask

    new_log = ErrorLog(
        module=module,
        message=str(exception),
        traceback=traceback.format_exc()
    )
    db.session.add(new_log)
    db.session.commit()
