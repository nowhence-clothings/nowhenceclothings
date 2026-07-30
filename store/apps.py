from django.apps import AppConfig


class StoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'

    def ready(self):
        # Optimise SQLite with WAL journal mode on every new connection
        from django.db.backends.signals import connection_created

        def _set_sqlite_pragmas(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                db_name = str(connection.settings_dict.get('NAME', ''))
                is_memory_db = db_name == ':memory:' or 'mode=memory' in db_name
                with connection.cursor() as cursor:
                    if not is_memory_db:
                        cursor.execute('PRAGMA journal_mode=WAL;')
                    cursor.execute('PRAGMA synchronous=NORMAL;')
                    cursor.execute('PRAGMA cache_size=-64000;')   # 64 MB
                    cursor.execute('PRAGMA busy_timeout=5000;')

        connection_created.connect(_set_sqlite_pragmas)

        # Register signals for email notifications
        import store.signals  # noqa: F401
