"""
Database Optimization

Provides query optimization, index optimization, connection pooling,
and caching strategies for SQLite and other databases.
"""

import logging
import sqlite3
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager
from queue import Queue
import threading

logger = logging.getLogger(__name__)


@dataclass
class QueryStats:
    """Query execution statistics"""
    query: str
    execution_time: float
    rows_returned: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ConnectionPool:
    """
    Connection pool for database connections.
    
    Provides:
    - Connection reuse
    - Connection limits
    - Health checks
    - Automatic recovery
    """
    
    def __init__(
        self,
        db_path: str,
        max_connections: int = 10,
        timeout: float = 5.0
    ):
        """
        Initialize connection pool.
        
        Args:
            db_path: Database path
            max_connections: Maximum pool size
            timeout: Connection timeout
        """
        self.db_path = db_path
        self.max_connections = max_connections
        self.timeout = timeout
        
        self.pool: Queue = Queue(maxsize=max_connections)
        self.active_connections = 0
        self.lock = threading.Lock()
        
        # Pre-create connections
        for _ in range(min(3, max_connections)):
            conn = self._create_connection()
            if conn:
                self.pool.put(conn)
        
        logger.info(f"ConnectionPool initialized (max: {max_connections})")
    
    def _create_connection(self) -> Optional[sqlite3.Connection]:
        """Create a new database connection"""
        try:
            conn = sqlite3.connect(
                self.db_path,
                timeout=self.timeout,
                check_same_thread=False
            )
            # Optimize SQLite settings
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            conn.execute("PRAGMA temp_store=MEMORY")
            return conn
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            return None
    
    @contextmanager
    def get_connection(self):
        """Get connection from pool (context manager)"""
        conn = None
        try:
            # Try to get from pool
            try:
                conn = self.pool.get(timeout=1.0)
            except:
                # Create new if pool empty and under limit
                with self.lock:
                    if self.active_connections < self.max_connections:
                        conn = self._create_connection()
                        if conn:
                            self.active_connections += 1
            
            if not conn:
                conn = self._create_connection()
            
            yield conn
            
        finally:
            if conn:
                try:
                    # Return to pool
                    self.pool.put(conn, block=False)
                except:
                    # Pool full, close connection
                    conn.close()
                    with self.lock:
                        self.active_connections -= 1
    
    def close_all(self):
        """Close all connections in pool"""
        while not self.pool.empty():
            conn = self.pool.get()
            conn.close()
        logger.info("All connections closed")


class DatabaseOptimizer:
    """
    Database optimizer for query and index optimization.
    
    Provides:
    - Query optimization
    - Index optimization
    - Query analysis
    - Performance monitoring
    """
    
    def __init__(self, db_path: str, connection_pool: Optional[ConnectionPool] = None):
        """
        Initialize database optimizer.
        
        Args:
            db_path: Database path
            connection_pool: Optional connection pool
        """
        self.db_path = db_path
        self.pool = connection_pool or ConnectionPool(db_path)
        self.query_stats: List[QueryStats] = []
        self.slow_query_threshold = 1.0  # seconds
        
        logger.info("DatabaseOptimizer initialized")
    
    def execute_query(
        self,
        query: str,
        parameters: Optional[Tuple] = None,
        fetch_all: bool = True
    ) -> List[Tuple]:
        """
        Execute optimized query.
        
        Args:
            query: SQL query
            parameters: Query parameters
            fetch_all: Whether to fetch all results
        
        Returns:
            Query results
        """
        start_time = time.time()
        
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                if parameters:
                    cursor.execute(query, parameters)
                else:
                    cursor.execute(query)
                
                if fetch_all:
                    results = cursor.fetchall()
                else:
                    results = cursor.fetchone()
                
                conn.commit()
                
                execution_time = time.time() - start_time
                
                # Record stats
                stats = QueryStats(
                    query=query[:100],  # Truncate for storage
                    execution_time=execution_time,
                    rows_returned=len(results) if isinstance(results, list) else 1
                )
                self.query_stats.append(stats)
                
                # Log slow queries
                if execution_time > self.slow_query_threshold:
                    logger.warning(
                        f"Slow query detected ({execution_time:.2f}s): {query[:100]}"
                    )
                
                return results
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Query execution failed: {e}")
                raise
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze query execution plan.
        
        Args:
            query: SQL query
        
        Returns:
            Analysis results
        """
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get EXPLAIN QUERY PLAN
            # Note: EXPLAIN QUERY PLAN doesn't support parameterized queries
            # This is for analysis only, not for user input
            if any(c in query for c in [';', '--', '/*', '*/', 'DROP', 'DELETE', 'INSERT', 'UPDATE']):
                raise ValueError("Invalid query for analysis")
            explain_query = f"EXPLAIN QUERY PLAN {query}"
            cursor.execute(explain_query)
            plan = cursor.fetchall()
            
            return {
                "query": query,
                "plan": plan,
                "estimated_cost": self._estimate_cost(plan)
            }
    
    def _estimate_cost(self, plan: List[Tuple]) -> float:
        """Estimate query cost from execution plan"""
        cost = 0.0
        
        for row in plan:
            # Simple cost estimation based on plan details
            if "SCAN TABLE" in str(row):
                cost += 10.0
            elif "SEARCH TABLE" in str(row):
                cost += 5.0
            elif "USE INDEX" in str(row):
                cost += 1.0
        
        return cost
    
    def optimize_indexes(self, table_name: str) -> List[str]:
        """
        Suggest index optimizations for a table.
        
        Args:
            table_name: Table name
        
        Returns:
            List of suggested CREATE INDEX statements
        """
        suggestions = []
        
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get table schema
            cursor.execute("PRAGMA table_info(?)", (table_name,))
            columns = cursor.fetchall()
            
            # Get existing indexes
            cursor.execute("PRAGMA index_list(?)", (table_name,))
            existing_indexes = [row[1] for row in cursor.fetchall()]
            
            # Analyze slow queries for this table
            table_queries = [
                q for q in self.query_stats
                if table_name in q.query.lower() and q.execution_time > 0.5
            ]
            
            # Suggest indexes for frequently queried columns
            column_usage = {}
            for query_stat in table_queries:
                # Simple heuristic: look for WHERE clauses
                query_lower = query_stat.query.lower()
                for col_name, _, _, _, _, _ in columns:
                    if f"where {col_name.lower()}" in query_lower:
                        column_usage[col_name] = column_usage.get(col_name, 0) + 1
            
            # Create index suggestions
            for col_name, usage_count in column_usage.items():
                if usage_count > 3:  # Used in multiple slow queries
                    index_name = f"idx_{table_name}_{col_name}"
                    if index_name not in existing_indexes:
                        suggestions.append(
                            f"CREATE INDEX {index_name} ON {table_name}({col_name})"
                        )
        
        return suggestions
    
    def get_performance_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get database performance statistics.
        
        Args:
            start_time: Start time filter
            end_time: End time filter
        
        Returns:
            Performance statistics
        """
        if start_time is None:
            start_time = datetime.utcnow().replace(hour=0, minute=0, second=0)
        if end_time is None:
            end_time = datetime.utcnow()
        
        filtered_stats = [
            s for s in self.query_stats
            if start_time <= s.timestamp <= end_time
        ]
        
        if not filtered_stats:
            return {"total_queries": 0}
        
        total_queries = len(filtered_stats)
        total_time = sum(s.execution_time for s in filtered_stats)
        avg_time = total_time / total_queries
        max_time = max(s.execution_time for s in filtered_stats)
        slow_queries = sum(1 for s in filtered_stats if s.execution_time > self.slow_query_threshold)
        
        return {
            "total_queries": total_queries,
            "total_time": total_time,
            "avg_time": avg_time,
            "max_time": max_time,
            "slow_queries": slow_queries,
            "slow_query_percentage": (slow_queries / total_queries * 100) if total_queries > 0 else 0
        }
    
    def vacuum_database(self):
        """Optimize database by running VACUUM"""
        logger.info("Running VACUUM to optimize database...")
        with self.pool.get_connection() as conn:
            conn.execute("VACUUM")
            conn.commit()
        logger.info("VACUUM completed")
    
    def analyze_database(self):
        """Run ANALYZE to update statistics"""
        logger.info("Running ANALYZE to update statistics...")
        with self.pool.get_connection() as conn:
            conn.execute("ANALYZE")
            conn.commit()
        logger.info("ANALYZE completed")

