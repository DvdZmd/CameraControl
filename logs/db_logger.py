import traceback
from database.models import ErrorLog, db
from flask import has_app_context

def log_error_to_db(module, exception):
    if not has_app_context():
        return  # prevenimos errores si se llama sin contexto de Flask

    new_log = ErrorLog(
        module=module,
        message=str(exception),
        traceback=traceback.format_exc()
    )
    db.session.add(new_log)
    db.session.commit()
