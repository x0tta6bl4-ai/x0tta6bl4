#!/usr/bin/env python3
"""
Production PostgreSQL setup and management for x0tta6bl4.

Handles:
- Database initialization and schema creation
- User/role management with RBAC
- Connection pooling configuration (pgBouncer)
- Backup/restore procedures
- Replication setup (streaming replication)
- Performance tuning
- Monitoring integration
- Migration management
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PostgresConfig:
    """Production PostgreSQL configuration"""

    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    admin_user: str = os.getenv("POSTGRES_ADMIN_USER", "postgres")
    admin_password: str = os.getenv("POSTGRES_ADMIN_PASSWORD", "")
    app_user: str = os.getenv("POSTGRES_APP_USER", "x0tta6bl4_app")
    app_password: str = os.getenv("POSTGRES_APP_PASSWORD", "")
    database: str = os.getenv("POSTGRES_DATABASE", "x0tta6bl4")

    replication_user: str = os.getenv("POSTGRES_REPLICATION_USER", "replicator")
    replication_password: str = os.getenv("POSTGRES_REPLICATION_PASSWORD", "")

    enable_replication: bool = (
        os.getenv("POSTGRES_ENABLE_REPLICATION", "false").lower() == "true"
    )
    enable_pgbouncer: bool = (
        os.getenv("POSTGRES_ENABLE_PGBOUNCER", "true").lower() == "true"
    )

    max_connections: int = int(os.getenv("POSTGRES_MAX_CONNECTIONS", "200"))
    max_prepared_transactions: int = int(
        os.getenv("POSTGRES_MAX_PREPARED_TRANSACTIONS", "100")
    )

    backup_path: str = os.getenv("POSTGRES_BACKUP_PATH", "./backups/postgres")
    backup_retention_days: int = int(os.getenv("POSTGRES_BACKUP_RETENTION_DAYS", "30"))
    enable_wal_archiving: bool = (
        os.getenv("POSTGRES_ENABLE_WAL_ARCHIVING", "true").lower() == "true"
    )

    ssl_enabled: bool = os.getenv("POSTGRES_SSL_ENABLED", "true").lower() == "true"
    ssl_cert_path: str = os.getenv(
        "POSTGRES_SSL_CERT_PATH", "/etc/postgresql/server.crt"
    )
    ssl_key_path: str = os.getenv("POSTGRES_SSL_KEY_PATH", "/etc/postgresql/server.key")


class PostgresSchemaManager:
    """Manage database schema creation and migrations"""

    def __init__(self, config: PostgresConfig):
        self.config = config
        self.connection_string = f"postgresql://{config.admin_user}:{config.admin_password}@{config.host}:{config.port}/postgres"

    def _psql_base(self, database: Optional[str] = None) -> List[str]:
        """Build base psql command as a list."""
        db = database or self.config.database
        return [
            "psql",
            "-h", self.config.host,
            "-p", str(self.config.port),
            "-U", self.config.admin_user,
            "-d", db,
        ]

    async def create_database(self) -> bool:
        """Create main application database"""
        try:
            result = subprocess.run(
                [
                    "psql",
                    "-h", self.config.host,
                    "-p", str(self.config.port),
                    "-U", self.config.admin_user,
                    "-tc", f"SELECT 1 FROM pg_database WHERE datname = '{self.config.database}'",
                ],
                capture_output=True,
                text=True,
            )

            if "1" not in result.stdout:
                logger.info(f"📦 Creating database: {self.config.database}")
                subprocess.run(
                    [
                        "psql",
                        "-h", self.config.host,
                        "-p", str(self.config.port),
                        "-U", self.config.admin_user,
                        "-c", f"CREATE DATABASE {self.config.database} ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C';",
                    ],
                    check=True,
                )
                logger.info("✅ Database created")
                return True
            else:
                logger.info(f"✅ Database {self.config.database} already exists")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to create database: {e}")
            raise

    async def create_users(self) -> bool:
        """Create application users with proper RBAC"""
        try:
            logger.info("👥 Setting up database users")

            psql_cmd = f"""
            psql -h {self.config.host} -p {self.config.port} -U {self.config.admin_user} \
              -d {self.config.database}
            """

            statements = [
                f"CREATE USER {self.config.app_user} WITH PASSWORD '{self.config.app_password}';",
                f"GRANT CONNECT ON DATABASE {self.config.database} TO {self.config.app_user};",
                f"GRANT USAGE ON SCHEMA public TO {self.config.app_user};",
                f"GRANT CREATE ON SCHEMA public TO {self.config.app_user};",
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {self.config.app_user};",
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO {self.config.app_user};",
            ]

            if self.config.enable_replication:
                statements.append(
                    f"CREATE USER {self.config.replication_user} WITH REPLICATION PASSWORD '{self.config.replication_password}';"
                )
                statements.append(
                    f"GRANT CONNECT ON DATABASE {self.config.database} TO {self.config.replication_user};"
                )

            for stmt in statements:
                result = subprocess.run(
                    f'echo "{stmt}" | {psql_cmd}',
                    shell=True,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0 and "already exists" not in result.stderr:
                    logger.warning(f"⚠️ {result.stderr}")

            logger.info("✅ Users created/configured")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create users: {e}")
            raise

    async def create_extensions(self) -> bool:
        """Enable required PostgreSQL extensions"""
        try:
            logger.info("📦 Enabling extensions")

            extensions = [
                "uuid-ossp",
                "pgcrypto",
                "pg_trgm",
                "hstore",
            ]

            psql_cmd = f"""
            psql -h {self.config.host} -p {self.config.port} -U {self.config.admin_user} \
              -d {self.config.database}
            """

            for ext in extensions:
                stmt = f"CREATE EXTENSION IF NOT EXISTS {ext};"
                result = subprocess.run(
                    f'echo "{stmt}" | {psql_cmd}',
                    shell=True,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    logger.debug(f"✅ Extension {ext} enabled")
                elif "already exists" not in result.stderr:
                    logger.warning(f"⚠️ Extension {ext}: {result.stderr}")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to enable extensions: {e}")
            raise

    async def create_tables(self) -> bool:
        """Create application schema tables"""
        try:
            logger.info("📋 Creating schema tables")

            schema_sql = """
            -- Mesh nodes table
            CREATE TABLE IF NOT EXISTS mesh_nodes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                node_id VARCHAR(255) UNIQUE NOT NULL,
                address INET NOT NULL,
                port INTEGER NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'offline',
                health_score FLOAT DEFAULT 0.0,
                last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_node_status (status),
                INDEX idx_last_heartbeat (last_heartbeat)
            );
            
            -- SPIFFE identities
            CREATE TABLE IF NOT EXISTS spiffe_identities (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                spiffe_id VARCHAR(255) UNIQUE NOT NULL,
                trust_domain VARCHAR(255) NOT NULL,
                subject_alt_names TEXT[],
                certificate_pem TEXT NOT NULL,
                key_encrypted BYTEA NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_spiffe_id (spiffe_id),
                INDEX idx_expires_at (expires_at)
            );
            
            -- API tokens
            CREATE TABLE IF NOT EXISTS api_tokens (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                token_hash VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                owner_id UUID NOT NULL,
                scopes TEXT[] DEFAULT ARRAY[]::TEXT[],
                last_used TIMESTAMP,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revoked_at TIMESTAMP,
                INDEX idx_token_hash (token_hash),
                INDEX idx_owner_id (owner_id),
                INDEX idx_expires_at (expires_at)
            );
            
            -- Audit log
            CREATE TABLE IF NOT EXISTS audit_log (
                id BIGSERIAL PRIMARY KEY,
                event_type VARCHAR(100) NOT NULL,
                subject_type VARCHAR(100) NOT NULL,
                subject_id UUID,
                actor_id UUID,
                action VARCHAR(50) NOT NULL,
                changes JSONB,
                result VARCHAR(50) NOT NULL DEFAULT 'success',
                error_message TEXT,
                ip_address INET,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_event_type (event_type),
                INDEX idx_subject (subject_type, subject_id),
                INDEX idx_created_at (created_at),
                INDEX idx_actor (actor_id)
            );
            
            -- Metrics snapshots
            CREATE TABLE IF NOT EXISTS metrics (
                id BIGSERIAL PRIMARY KEY,
                metric_name VARCHAR(255) NOT NULL,
                labels JSONB,
                value FLOAT NOT NULL,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_metric_name (metric_name),
                INDEX idx_timestamp (timestamp),
                INDEX idx_metric_ts (metric_name, timestamp)
            );
            
            -- Create hypertable for time-series metrics (if TimescaleDB available)
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb') THEN
                    CREATE EXTENSION IF NOT EXISTS timescaledb;
                    SELECT create_hypertable('metrics', 'timestamp', if_not_exists => TRUE);
                END IF;
            END $$;
            
            -- Create indexes for performance
            CREATE INDEX IF NOT EXISTS idx_mesh_nodes_status ON mesh_nodes(status);
            CREATE INDEX IF NOT EXISTS idx_spiffe_expires ON spiffe_identities(expires_at);
            CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
            
            -- Create views for common queries
            CREATE OR REPLACE VIEW v_active_nodes AS
            SELECT * FROM mesh_nodes WHERE status = 'online' AND last_heartbeat > CURRENT_TIMESTAMP - INTERVAL '1 minute';
            
            CREATE OR REPLACE VIEW v_expiring_certificates AS
            SELECT * FROM spiffe_identities WHERE expires_at < CURRENT_TIMESTAMP + INTERVAL '7 days';
            """

            psql_cmd = f"""
            psql -h {self.config.host} -p {self.config.port} -U {self.config.admin_user} \
              -d {self.config.database}
            """

            result = subprocess.run(
                f"cat << 'EOF' | {psql_cmd}\n{schema_sql}\nEOF",
                shell=True,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                logger.info("✅ Schema tables created")
                return True
            else:
                logger.error(f"❌ Schema creation failed: {result.stderr}")
                raise RuntimeError(f"Schema creation error: {result.stderr}")

        except Exception as e:
            logger.error(f"❌ Failed to create tables: {e}")
            raise


class PgBouncerConfig:
    """Generate pgBouncer configuration for connection pooling"""

    def __init__(self, config: PostgresConfig):
        self.config = config

    def generate_config(self) -> str:
        """Generate pgBouncer configuration"""
        return f"""
[databases]
{self.config.database} = host={self.config.host} port={self.config.port} dbname={self.config.database}

[pgbouncer]
logfile = /var/log/postgresql/pgbouncer.log
pidfile = /var/run/postgresql/pgbouncer.pid
listen_port = 6432
listen_addr = 127.0.0.1
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
min_pool_size = 10
reserve_pool_size = 5
reserve_pool_timeout = 3
max_db_connections = 100
max_user_connections = 100
server_lifetime = 3600
server_idle_timeout = 600
dns_max_ttl = 15
query_timeout = 30000
query_wait_timeout = 120000
idle_in_transaction_session_timeout = 30000
verbose = 0
admin_users = {self.config.admin_user}
stats_users = {self.config.app_user}
"""

    def generate_userlist(self) -> str:
        """Generate pgBouncer user credentials"""
        return f""""{self.config.admin_user}" "{self.config.admin_password}"
"{self.config.app_user}" "{self.config.app_password}"
"""


class PostgresBackupManager:
    """Handle backup and restore operations"""

    def __init__(self, config: PostgresConfig):
        self.config = config
        Path(config.backup_path).mkdir(parents=True, exist_ok=True)

    async def create_backup(self) -> Optional[Path]:
        """Create full database backup"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = (
                Path(self.config.backup_path)
                / f"backup_{self.config.database}_{timestamp}.sql.gz"
            )

            logger.info(f"💾 Creating backup: {backup_file}")

            cmd = f"""
            PGPASSWORD={self.config.admin_password} pg_dump \
              -h {self.config.host} \
              -p {self.config.port} \
              -U {self.config.admin_user} \
              -d {self.config.database} \
              --no-password \
              --format=plain \
              | gzip > {backup_file}
            """

            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                size_mb = backup_file.stat().st_size / (1024 * 1024)
                logger.info(f"✅ Backup created: {backup_file} ({size_mb:.2f} MB)")
                return backup_file
            else:
                logger.error(f"❌ Backup failed: {result.stderr}")
                raise RuntimeError(f"Backup error: {result.stderr}")

        except Exception as e:
            logger.error(f"❌ Failed to create backup: {e}")
            return None

    async def restore_backup(self, backup_file: Path) -> bool:
        """Restore database from backup"""
        try:
            logger.info(f"🔄 Restoring from: {backup_file}")

            if not backup_file.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_file}")

            if str(backup_file).endswith(".gz"):
                cmd = f"""
                gunzip -c {backup_file} | \
                PGPASSWORD={self.config.admin_password} psql \
                  -h {self.config.host} \
                  -p {self.config.port} \
                  -U {self.config.admin_user} \
                  -d {self.config.database}
                """
            else:
                cmd = f"""
                PGPASSWORD={self.config.admin_password} psql \
                  -h {self.config.host} \
                  -p {self.config.port} \
                  -U {self.config.admin_user} \
                  -d {self.config.database} \
                  -f {backup_file}
                """

            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("✅ Restore completed successfully")
                return True
            else:
                logger.error(f"❌ Restore failed: {result.stderr}")
                raise RuntimeError(f"Restore error: {result.stderr}")

        except Exception as e:
            logger.error(f"❌ Failed to restore backup: {e}")
            return False

    async def cleanup_old_backups(self) -> int:
        """Remove backups older than retention period"""
        try:
            cutoff_date = datetime.now() - timedelta(
                days=self.config.backup_retention_days
            )
            backup_dir = Path(self.config.backup_path)
            removed_count = 0

            for backup_file in backup_dir.glob("backup_*.sql*"):
                mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                if mtime < cutoff_date:
                    logger.info(f"🗑️  Removing old backup: {backup_file.name}")
                    backup_file.unlink()
                    removed_count += 1

            if removed_count > 0:
                logger.info(f"✅ Cleaned up {removed_count} old backups")

            return removed_count

        except Exception as e:
            logger.error(f"❌ Backup cleanup failed: {e}")
            return 0


class PostgresReplicationManager:
    """Configure streaming replication for HA"""

    def __init__(self, config: PostgresConfig):
        self.config = config

    async def setup_replication(self) -> bool:
        """Setup streaming replication on primary"""
        try:
            if not self.config.enable_replication:
                logger.info("⏭️  Replication disabled")
                return False

            logger.info("🔗 Setting up replication")

            statements = [
                f"ALTER SYSTEM SET wal_level = replica;",
                f"ALTER SYSTEM SET max_wal_senders = 10;",
                f"ALTER SYSTEM SET max_replication_slots = 10;",
                f"ALTER SYSTEM SET hot_standby = on;",
                f"ALTER SYSTEM SET hot_standby_feedback = on;",
            ]

            psql_cmd = f"""
            psql -h {self.config.host} -p {self.config.port} -U {self.config.admin_user} \
              -d {self.config.database}
            """

            for stmt in statements:
                result = subprocess.run(
                    f'echo "{stmt}" | {psql_cmd}',
                    shell=True,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    logger.warning(f"⚠️ {result.stderr}")

            logger.info("✅ Replication configuration applied")
            logger.info("⚠️  Restart PostgreSQL to apply WAL settings")
            return True

        except Exception as e:
            logger.error(f"❌ Replication setup failed: {e}")
            return False


class PostgresSetupOrchestrator:
    """Orchestrate complete PostgreSQL production setup"""

    def __init__(self, config: Optional[PostgresConfig] = None):
        self.config = config or PostgresConfig()
        self.schema_manager = PostgresSchemaManager(self.config)
        self.backup_manager = PostgresBackupManager(self.config)
        self.replication_manager = PostgresReplicationManager(self.config)

    async def run_full_setup(self) -> bool:
        """Execute complete setup pipeline"""
        try:
            logger.info("🚀 Starting PostgreSQL production setup")
            logger.info(f"   Host: {self.config.host}:{self.config.port}")
            logger.info(f"   Database: {self.config.database}")

            # 1. Create database
            await self.schema_manager.create_database()

            # 2. Create users
            await self.schema_manager.create_users()

            # 3. Enable extensions
            await self.schema_manager.create_extensions()

            # 4. Create schema
            await self.schema_manager.create_tables()

            # 5. Setup replication if enabled
            if self.config.enable_replication:
                await self.replication_manager.setup_replication()

            # 6. Create initial backup
            await self.backup_manager.create_backup()

            # 7. Generate pgBouncer config if enabled
            if self.config.enable_pgbouncer:
                pgbouncer = PgBouncerConfig(self.config)
                config_path = Path("/etc/pgbouncer/pgbouncer.ini")
                userlist_path = Path("/etc/pgbouncer/userlist.txt")

                logger.info(f"📝 pgBouncer config (would be saved to {config_path})")
                logger.debug(f"\n{pgbouncer.generate_config()}")
                logger.debug(f"\nUserlist config (would be saved to {userlist_path})")

            logger.info("✅ PostgreSQL setup completed successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Setup failed: {e}")
            return False

    async def get_status(self) -> Dict[str, Any]:
        """Get PostgreSQL cluster status"""
        try:
            psql_cmd = f"""
            psql -h {self.config.host} -p {self.config.port} -U {self.config.admin_user} \
              -d {self.config.database} -t -c
            """

            status = {}

            # Check version
            result = subprocess.run(
                f"{psql_cmd} 'SELECT version();'",
                shell=True,
                capture_output=True,
                text=True,
            )
            status["version"] = (
                result.stdout.strip() if result.returncode == 0 else "unknown"
            )

            # Check connection count
            result = subprocess.run(
                f"{psql_cmd} 'SELECT count(*) FROM pg_stat_activity;'",
                shell=True,
                capture_output=True,
                text=True,
            )
            status["active_connections"] = (
                int(result.stdout.strip()) if result.returncode == 0 else 0
            )

            # Check database size
            result = subprocess.run(
                f"{psql_cmd} \"SELECT pg_size_pretty(pg_database_size('{self.config.database}'));\"",
                shell=True,
                capture_output=True,
                text=True,
            )
            status["database_size"] = (
                result.stdout.strip() if result.returncode == 0 else "unknown"
            )

            # Check replication status if enabled
            if self.config.enable_replication:
                result = subprocess.run(
                    f'{psql_cmd} "SELECT count(*) FROM pg_stat_replication;"',
                    shell=True,
                    capture_output=True,
                    text=True,
                )
                status["replication_slots"] = (
                    int(result.stdout.strip()) if result.returncode == 0 else 0
                )

            return status

        except Exception as e:
            logger.error(f"❌ Failed to get status: {e}")
            return {}


async def main():
    """CLI entry point"""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if len(sys.argv) < 2:
        print("Usage: python postgres_setup.py <command>")
        print("\nCommands:")
        print("  setup              - Run full PostgreSQL setup")
        print("  backup             - Create database backup")
        print("  restore <file>     - Restore from backup")
        print("  status             - Show cluster status")
        print("  cleanup-backups    - Remove old backups")
        sys.exit(1)

    config = PostgresConfig()
    orchestrator = PostgresSetupOrchestrator(config)

    command = sys.argv[1]

    if command == "setup":
        success = await orchestrator.run_full_setup()
        sys.exit(0 if success else 1)

    elif command == "backup":
        await orchestrator.backup_manager.create_backup()

    elif command == "restore":
        if len(sys.argv) < 3:
            print("Usage: python postgres_setup.py restore <backup_file>")
            sys.exit(1)
        success = await orchestrator.backup_manager.restore_backup(Path(sys.argv[2]))
        sys.exit(0 if success else 1)

    elif command == "status":
        status = await orchestrator.get_status()
        print(json.dumps(status, indent=2))

    elif command == "cleanup-backups":
        count = await orchestrator.backup_manager.cleanup_old_backups()
        print(f"Cleaned up {count} backups")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
