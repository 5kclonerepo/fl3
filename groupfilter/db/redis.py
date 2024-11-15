# Copyright (C) 2024 @jithumon

import redis

class NamespacedRedis(redis.Redis):
    def __init__(self, namespace: str, *args, **kwargs):
        self.namespace = f"bot:{namespace}:"
        super().__init__(*args, **kwargs)

    def _apply_namespace(self, key):
        """Private method to apply namespace to the key."""
        return self.namespace + key

    def set(self, name, value, *args, **kwargs):
        return super().set(self._apply_namespace(name), value, *args, **kwargs)

    def get(self, name, *args, **kwargs):
        return super().get(self._apply_namespace(name), *args, **kwargs)

    def delete(self, *names):
        names_with_namespace = [self._apply_namespace(name) for name in names]
        return super().delete(*names_with_namespace)

    def hset(self, name, key, value, *args, **kwargs):
        return super().hset(self._apply_namespace(name), key, value, *args, **kwargs)

    def hget(self, name, key, *args, **kwargs):
        return super().hget(self._apply_namespace(name), key, *args, **kwargs)

