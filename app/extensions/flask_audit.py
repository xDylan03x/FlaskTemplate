import copy
from contextlib import contextmanager
from flask import g, has_request_context, current_app
from sqlalchemy.orm import sessionmaker


class AuditManager:
    def __init__(self, app=None, db=None):
        self.app = app
        self.db = db
        self._audit_session_factory = None

        if app is not None and db is not None:
            self.init_app(app, db)

    def init_app(self, app, db):
        self.app = app
        self.db = db
        with app.app_context():
            self._audit_session_factory = sessionmaker(
                bind=self.db.engine,
                expire_on_commit=False,
            )
        app.extensions["audit"] = self

        app.before_request(self._start_request)
        app.after_request(self._after_request)
        app.teardown_request(self._teardown_request)

    def _create_audit_session(self):
        if self._audit_session_factory is None:
            raise RuntimeError("AuditManager is not initialized.")
        return self._audit_session_factory()

    def _start_request(self):
        g.audit_records = []

    def _after_request(self, response):
        self.flush()
        return response

    def _teardown_request(self, exception=None):
        if has_request_context():
            g.audit_records = []

    def _record(self, message: str):
        if has_request_context():
            if not hasattr(g, "audit_records"):
                self._start_request()

            g.audit_records.append(message)
        else:
            self._save_record(message)

    def _save_record(self, message: str):
        from ..models import AuditEvent

        session = self._create_audit_session()
        try:
            session.add(AuditEvent(message=message))
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def flush(self):
        if not has_request_context():
            return

        records = getattr(g, "audit_records", [])
        if not records:
            return

        try:
            for record in records:
                self._save_record(record)

            g.audit_records = []
        except Exception:
            current_app.logger.exception("Failed to save audit logs.")

    def log(self, message: str, target: object = None, actor: object = None):
        audit_record = {
            "target_type": type(target).__name__,
            "target_repr": str(target),
            "actor": str(actor) if actor else "System",
            "message": message
        }
        self._record(self._create_audit_message(audit_record))

    @contextmanager
    def track(self, target: object, actor: object = None, message: str = None):
        """
        Track the target object as changes are made throughout it.
        Safely handles __dict__, __slots__, and primitive types.
        Captures deep mutations (nested dicts/lists).

        Usage:
            with audit.track(user, message="Updated user"):
                user.name = form.name.data

        :param target: The object to track
        :param actor: The user who made the changes (optional if the system is the actor)
        """
        before_state = self._get_state(target)

        try:
            yield target
        finally:
            after_state = self._get_state(target)
            differences = {}

            if isinstance(before_state, dict) and isinstance(after_state, dict):
                # Handle objects (__dict__ or __slots__)
                all_keys = set(before_state.keys()) | set(after_state.keys())
                for k in all_keys:
                    b_val = before_state.get(k)
                    a_val = after_state.get(k)
                    if b_val != a_val:
                        differences[k] = {"before": b_val, "after": a_val}
            else:
                # Handle direct primitives/collections if they were mutated/reassigned
                if before_state != after_state:
                    differences["root_value"] = {"before": before_state, "after": after_state}

            audit_record = {
                "message": message,
                "target_type": type(target).__name__,
                "target_repr": str(target),
                "actor": str(actor) if actor else "System",
                "state_before": before_state,
                "state_after": after_state,
                "differences": differences,
                "has_changes": len(differences) > 0
            }

            self._record(self._create_audit_message(audit_record))

    def _get_state(self, target: object):
        if hasattr(target, '__dict__'):
            return copy.deepcopy(target.__dict__)
        elif hasattr(target, '__slots__'):
            slots = [target.__slots__] if isinstance(target.__slots__, str) else target.__slots__
            return {slot: copy.deepcopy(getattr(target, slot)) for slot in slots if hasattr(target, slot)}
        else:
            return copy.deepcopy(target)

    def _create_audit_message(self, record: dict) -> str:
        """
        Centralized method to handle the recorded data.
        """
        log_lines = []
        if "target_type" in record:
            log_lines.append(f"Target Type: {record['target_type']}")
        if "target_repr" in record:
            log_lines.append(f"Target Representation: {record['target_repr']}")
        if "actor" in record:
            log_lines.append(f"Actor: {record['actor']}")
        if "message" in record:
            log_lines.append(f"Message: {record['message']}")
        if "has_changes" in record:
            log_lines.append(f"Has Changes: {record['has_changes']}")
        if "differences" in record:
            log_lines.append(f"Differences: {record['differences']}")
        if "state_before" in record:
            log_lines.append(f"Full Snapshot Before: {record['state_before']}")
        if "state_after" in record:
            log_lines.append(f"Full Snapshot After:  {record['state_after']}")
        log_str = "\n".join(log_lines)
        # if self.app.config['DEBUG']:
        #     print("--------------- Start Log Message ---------------")
        #     print(log_str)
        #     print("---------------- End Log Message ----------------")
        return log_str

