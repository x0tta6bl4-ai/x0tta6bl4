"""
SPIRE Server Client

Production-ready client for SPIRE Server API:
- Entry management
- Registration
- Health checks
- Server status
"""
import logging
import subprocess
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SPIREServerEntry:
    """SPIRE Server entry"""
    entry_id: str
    spiffe_id: str
    parent_id: str
    selectors: Dict[str, str]
    ttl: int
    admin: bool = False


class SPIREServerClient:
    """
    Client for SPIRE Server API.
    
    Provides production-ready integration with SPIRE Server:
    - Entry management (create, list, delete)
    - Registration operations
    - Health checks
    - Server status
    """
    
    def __init__(
        self,
        server_address: str = "127.0.0.1:8081",
        server_socket: Optional[Path] = None,
        spire_server_bin: str = "spire-server"
    ):
        """
        Initialize SPIRE Server client.
        
        Args:
            server_address: SPIRE Server address (host:port)
            server_socket: Path to SPIRE Server Unix socket (optional)
            spire_server_bin: Path to spire-server binary
        """
        self.server_address = server_address
        self.server_socket = server_socket
        self.spire_server_bin = spire_server_bin
        
        logger.info(f"SPIRE Server Client initialized for {server_address}")
    
    def health_check(self) -> bool:
        """
        Check SPIRE Server health.
        
        Returns:
            True if server is healthy
        """
        try:
            result = subprocess.run(
                [self.spire_server_bin, "healthcheck"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"SPIRE Server health check failed: {e}")
            return False
    
    def create_entry(
        self,
        spiffe_id: str,
        parent_id: str,
        selectors: Dict[str, str],
        ttl: int = 3600,
        admin: bool = False
    ) -> Optional[str]:
        """
        Create a new entry in SPIRE Server.
        
        Args:
            spiffe_id: SPIFFE ID for the entry
            parent_id: Parent SPIFFE ID
            selectors: Workload selectors (e.g., {"unix:uid": "1000"})
            ttl: SVID time-to-live in seconds
            admin: Whether entry has admin privileges
        
        Returns:
            Entry ID if successful, None otherwise
        """
        try:
            # Build selector string
            selector_str = ",".join([f"{k}:{v}" for k, v in selectors.items()])
            
            # Build command
            cmd = [
                self.spire_server_bin,
                "entry", "create",
                "-spiffeID", spiffe_id,
                "-parentID", parent_id,
                "-selector", selector_str,
                "-ttl", str(ttl)
            ]
            
            if admin:
                cmd.append("-admin")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Extract entry ID from output
                # Format: "Entry created: <entry-id>"
                entry_id = result.stdout.strip().split()[-1] if result.stdout else None
                logger.info(f"Created SPIRE entry: {spiffe_id} (ID: {entry_id})")
                return entry_id
            else:
                logger.error(f"Failed to create entry: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Error creating SPIRE entry: {e}")
            return None
    
    def list_entries(self) -> List[SPIREServerEntry]:
        """
        List all entries in SPIRE Server.
        
        Returns:
            List of SPIREServerEntry objects
        """
        try:
            result = subprocess.run(
                [self.spire_server_bin, "entry", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning(f"Failed to list entries: {result.stderr}")
                return []
            
            # Parse output
            entries = []
            current_entry = {}
            
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if not line:
                    if current_entry:
                        entries.append(self._parse_entry(current_entry))
                        current_entry = {}
                    continue
                
                if ':' in line:
                    key, value = line.split(':', 1)
                    current_entry[key.strip()] = value.strip()
            
            if current_entry:
                entries.append(self._parse_entry(current_entry))
            
            logger.info(f"Listed {len(entries)} SPIRE entries")
            return entries
        except Exception as e:
            logger.error(f"Error listing SPIRE entries: {e}")
            return []
    
    def delete_entry(self, entry_id: str) -> bool:
        """
        Delete an entry from SPIRE Server.
        
        Args:
            entry_id: Entry ID to delete
        
        Returns:
            True if deletion successful
        """
        try:
            result = subprocess.run(
                [self.spire_server_bin, "entry", "delete", "-entryID", entry_id],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info(f"Deleted SPIRE entry: {entry_id}")
                return True
            else:
                logger.error(f"Failed to delete entry: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error deleting SPIRE entry: {e}")
            return False
    
    def _parse_entry(self, entry_dict: Dict[str, str]) -> SPIREServerEntry:
        """Parse entry dictionary into SPIREServerEntry"""
        selectors = {}
        selectors_str = entry_dict.get("Selectors", "")
        if selectors_str:
            for s in selectors_str.split(','):
                if ':' in s:
                    parts = s.split(':', 1)
                    if len(parts) == 2:
                        selectors[parts[0].strip()] = parts[1].strip()
        
        return SPIREServerEntry(
            entry_id=entry_dict.get("Entry ID", ""),
            spiffe_id=entry_dict.get("SPIFFE ID", ""),
            parent_id=entry_dict.get("Parent ID", ""),
            selectors=selectors,
            ttl=int(entry_dict.get("TTL", "3600")),
            admin=entry_dict.get("Admin", "false").lower() == "true"
        )
    
    def get_server_status(self) -> Dict[str, Any]:
        """
        Get SPIRE Server status.
        
        Returns:
            Dictionary with server status information
        """
        try:
            result = subprocess.run(
                [self.spire_server_bin, "healthcheck", "-shallow"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            return {
                "healthy": result.returncode == 0,
                "address": self.server_address,
                "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
            }
        except Exception as e:
            logger.error(f"Error getting server status: {e}")
            return {
                "healthy": False,
                "address": self.server_address,
                "error": str(e)
            }

