# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from mysql.connector import MySQLConnection
from mysql.connector.pooling import PooledMySQLConnection
from logging import getLogger
import os

logger = getLogger(__name__)

def apply_migrations(cnx: MySQLConnection | PooledMySQLConnection,
                    migrations_dir: str = "migrations") -> tuple[int, int]:
    """
    Apply database migrations in the specified directory.
    Args:
        cnx (MySQLConnection): The MySQL connection object.
        migrations_dir (str): The directory containing migration files.
    Returns:
        tuple: A tuple containing the number of migrations applied and the number of migration commands ran.

    """
    
    cursor = cnx.cursor()

    migrations_applied = 0
    migration_commands_ran = 0
    
    for migration_file in sorted(os.listdir(migrations_dir)):
        if migration_file.endswith(".sql"):
            with open(os.path.join(migrations_dir, migration_file), 'r') as file:
                migration_in_file = 0
                migration_sql = file.read()
                migration_sql_commands = migration_sql.split(';')
                migration_sql_commands = [cmd.strip() for cmd in migration_sql_commands if cmd.strip()]
                try:
                    for command in migration_sql_commands:
                        migration_in_file += 1
                        logger.debug(f"Executing migration command #{migration_in_file} in file {migration_file}")
                        cursor.execute(command)
                        migration_commands_ran += 1
                    cnx.commit()
                    migrations_applied += 1
                    logger.info(f"Applied migration: {migration_file}")
                except Exception as e:
                    logger.error(f"Failed to apply migration {migration_file}: {e}")
                    cnx.rollback()

    return migrations_applied, migration_commands_ran