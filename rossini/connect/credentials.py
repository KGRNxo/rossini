"""Credentials for self-hosted services (WebDAV). Stored only on the data partition, file mode 0600,
never in settings.json or logs.
shortcut: not encrypted at rest (no hardware key store is available); upgrade with a device-bound key once a BSP provides one."""
import json
import os

from ..common import atomic_write


class Credentials:
    def __init__(self, path):
        self.path = path

    def _load(self):
        try:
            with open(self.path) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def get(self, service):
        v = self._load().get(service)
        return (v["user"], v["password"]) if v else (None, None)

    def set(self, service, user, password):
        data = self._load()
        data[service] = {"user": user, "password": password}
        atomic_write(self.path, json.dumps(data).encode())
        os.chmod(self.path, 0o600)

    def delete(self, service):
        data = self._load()
        if data.pop(service, None) is not None:
            atomic_write(self.path, json.dumps(data).encode())
            os.chmod(self.path, 0o600)
