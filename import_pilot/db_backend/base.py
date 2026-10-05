from django.core.exceptions import ImproperlyConfigured
from django.db.backends.postgresql.base import DatabaseWrapper as PostgreSQLWrapper


class DatabaseWrapper(PostgreSQLWrapper):
    def get_new_connection(self, conn_params):
        connection = super().get_new_connection(conn_params)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT current_user, session_user,
                           current_setting('search_path'), current_schema(),
                           EXISTS(SELECT 1 FROM pg_namespace
                                  WHERE nspname = 'import_pilot')
                    """
                )
                user, session_user, path, schema, exists = cursor.fetchone()
                if (
                    user != "import_pilot_role"
                    or session_user != "import_pilot_role"
                    or path != "import_pilot"
                    or schema != "import_pilot"
                    or not exists
                ):
                    raise ImproperlyConfigured(
                        "Pilot requires a direct pilot-role connection and exact pilot schema."
                    )
                cursor.execute(
                    """
                    SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication,
                           rolbypassrls,
                           EXISTS(SELECT 1 FROM pg_auth_members
                                  WHERE member = r.oid)
                    FROM pg_roles r WHERE rolname = current_user
                    """
                )
                role_flags = cursor.fetchone()
                if role_flags is None or any(role_flags):
                    raise ImproperlyConfigured("Pilot role has prohibited privileges.")
                cursor.execute(
                    """
                    SELECT has_schema_privilege(current_user, 'public', 'CREATE')
                    OR EXISTS(
                        SELECT 1 FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE n.nspname = 'public'
                          AND c.relkind IN ('r','p','v','m','f')
                          AND has_table_privilege(
                              current_user, c.oid,
                              'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                    )
                    OR EXISTS(
                        SELECT 1 FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE n.nspname = 'public' AND c.relkind = 'S'
                          AND has_sequence_privilege(current_user, c.oid, 'USAGE,UPDATE')
                    )
                    OR EXISTS(
                        SELECT 1 FROM pg_proc p
                        JOIN pg_namespace n ON n.oid = p.pronamespace
                        WHERE n.nspname = 'public' AND p.prosecdef
                          AND has_function_privilege(current_user, p.oid, 'EXECUTE')
                    )
                    """
                )
                if cursor.fetchone()[0]:
                    raise ImproperlyConfigured("Pilot can write or escalate into public.")
            # Django configures autocommit after get_new_connection returns.
            # Do not leave our inspection SELECTs in an open transaction.
            if not connection.autocommit:
                connection.rollback()
        except Exception:
            connection.close()
            raise
        return connection
