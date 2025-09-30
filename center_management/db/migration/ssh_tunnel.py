#!/usr/bin/env python3
"""
SSH Tunnel Manager for Database Port Forwarding

This module provides SSH tunnel functionality to securely connect to remote
PostgreSQL databases through a gateway/bastion host using port forwarding.

Usage:
    with SSHTunnelManager(config) as tunnel:
        # Use tunnel.local_bind_port to connect to the remote database
        conn = psycopg2.connect(host='localhost', port=tunnel.local_bind_port, ...)
"""

import os
import socket
import threading
import time
from pathlib import Path
from typing import Optional
import paramiko
from loguru import logger


class SSHTunnelError(Exception):
    """SSH Tunnel related errors"""
    pass


class SSHTunnelManager:
    """
    SSH Tunnel Manager for PostgreSQL port forwarding

    Forwards a local port to a remote PostgreSQL server through an SSH gateway.
    """

    def __init__(self, gateway_host: str, gateway_port: int = 22,
                 gateway_user: str = 'root', key_file: Optional[str] = None,
                 remote_host: str = 'db', remote_port: int = 5438,
                 local_port: int = 5439, timeout: int = 30):
        """
        Initialize SSH tunnel manager

        Args:
            gateway_host: SSH gateway/bastion host IP or hostname
            gateway_port: SSH port on gateway (default: 22)
            gateway_user: SSH username for gateway (default: 'root')
            key_file: Path to SSH private key file
            remote_host: Remote database host (as seen from gateway, default: 'db')
            remote_port: Remote database port (default: 5438)
            local_port: Local port to bind for forwarding (default: 5439)
            timeout: Connection timeout in seconds (default: 30)
        """
        self.gateway_host = gateway_host
        self.gateway_port = gateway_port
        self.gateway_user = gateway_user
        self.key_file = key_file
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.local_port = local_port
        self.timeout = timeout

        self._ssh_client: Optional[paramiko.SSHClient] = None
        self._transport: Optional[paramiko.Transport] = None
        self._server_socket: Optional[socket.socket] = None
        self._tunnel_thread: Optional[threading.Thread] = None
        self._stop_tunnel = threading.Event()
        self._tunnel_active = False

    def start(self) -> int:
        """
        Start SSH tunnel

        Returns:
            Local bind port number

        Raises:
            SSHTunnelError: If tunnel creation fails
        """
        if self._tunnel_active:
            logger.warning("SSH tunnel already active")
            return self.local_port

        try:
            # Establish SSH connection
            self._connect_ssh()

            # Create local listening socket
            self._create_local_socket()

            # Start tunnel forwarding thread
            self._start_tunnel_thread()

            self._tunnel_active = True
            logger.success(
                f"SSH tunnel established: localhost:{self.local_port} -> "
                f"{self.gateway_host} -> {self.remote_host}:{self.remote_port}"
            )

            return self.local_port

        except Exception as e:
            self._cleanup()
            raise SSHTunnelError(f"Failed to start SSH tunnel: {e}")

    def stop(self) -> None:
        """Stop SSH tunnel and cleanup resources"""
        if not self._tunnel_active:
            return

        logger.info("Stopping SSH tunnel...")
        self._stop_tunnel.set()

        # Wait for tunnel thread to finish
        if self._tunnel_thread and self._tunnel_thread.is_alive():
            self._tunnel_thread.join(timeout=5)

        self._cleanup()
        self._tunnel_active = False
        logger.info("SSH tunnel stopped")

    def is_active(self) -> bool:
        """Check if tunnel is active"""
        return self._tunnel_active

    def _connect_ssh(self) -> None:
        """Establish SSH connection to gateway"""
        self._ssh_client = paramiko.SSHClient()
        self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            'hostname': self.gateway_host,
            'port': self.gateway_port,
            'username': self.gateway_user,
            'timeout': self.timeout,
        }

        # Load private key if provided
        if self.key_file:
            pkey = self._load_private_key(self.key_file)
            if pkey:
                connect_kwargs['pkey'] = pkey
            else:
                connect_kwargs['key_filename'] = self.key_file

        logger.info(f"Connecting to SSH gateway: {self.gateway_user}@{self.gateway_host}:{self.gateway_port}")
        self._ssh_client.connect(**connect_kwargs)
        self._transport = self._ssh_client.get_transport()

        if not self._transport:
            raise SSHTunnelError("Failed to get SSH transport")

        logger.info("SSH connection established")

    def _load_private_key(self, key_file: str) -> Optional[paramiko.PKey]:
        """
        Load SSH private key

        Args:
            key_file: Path to private key file

        Returns:
            Paramiko PKey instance or None
        """
        if not key_file:
            return None
        
        # Expand tilde to home directory
        key_path = Path(key_file).expanduser()
        if not key_path.exists():
            return None

        key_classes = [
            getattr(paramiko, 'RSAKey', None),
            getattr(paramiko, 'Ed25519Key', None),
            getattr(paramiko, 'ECDSAKey', None),
            getattr(paramiko, 'DSSKey', None),
        ]

        # Check for OpenSSH format
        try:
            with open(key_path, 'r', encoding='utf-8', errors='ignore') as f:
                head = f.read(512)
                if 'BEGIN OPENSSH PRIVATE KEY' in head:
                    logger.debug(f"Key {key_path} is OpenSSH format; using key_filename")
                    return None
        except Exception:
            pass

        # Try loading with each key class
        for cls in key_classes:
            if not cls:
                continue
            try:
                pkey = cls.from_private_key_file(str(key_path))
                logger.debug(f"Successfully loaded key with {cls.__name__}")
                return pkey
            except Exception as e:
                logger.debug(f"Key loader {cls.__name__} failed: {e}")

        return None

    def _create_local_socket(self) -> None:
        """Create local listening socket"""
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self._server_socket.bind(('127.0.0.1', self.local_port))
            self._server_socket.listen(5)
            self._server_socket.settimeout(1.0)  # For periodic checking
            logger.info(f"Local socket listening on 127.0.0.1:{self.local_port}")
        except OSError as e:
            raise SSHTunnelError(f"Failed to bind local port {self.local_port}: {e}")

    def _start_tunnel_thread(self) -> None:
        """Start tunnel forwarding thread"""
        self._stop_tunnel.clear()
        self._tunnel_thread = threading.Thread(
            target=self._tunnel_worker,
            daemon=True,
            name="SSHTunnelForwarder"
        )
        self._tunnel_thread.start()
        logger.info("Tunnel forwarding thread started")

    def _tunnel_worker(self) -> None:
        """Worker thread that handles tunnel forwarding"""
        logger.info("Tunnel worker started")

        while not self._stop_tunnel.is_set():
            try:
                # Accept connections with timeout
                try:
                    client_socket, client_addr = self._server_socket.accept()
                except socket.timeout:
                    continue  # Check stop flag and retry
                except Exception as e:
                    if not self._stop_tunnel.is_set():
                        logger.error(f"Error accepting connection: {e}")
                    break

                logger.debug(f"Accepted connection from {client_addr}")

                # Create forwarding channel
                try:
                    channel = self._transport.open_channel(
                        'direct-tcpip',
                        (self.remote_host, self.remote_port),
                        client_addr
                    )
                except Exception as e:
                    logger.error(f"Failed to open SSH channel: {e}")
                    client_socket.close()
                    continue

                # Start forwarding in a separate thread
                forward_thread = threading.Thread(
                    target=self._forward_connection,
                    args=(client_socket, channel),
                    daemon=True
                )
                forward_thread.start()

            except Exception as e:
                if not self._stop_tunnel.is_set():
                    logger.error(f"Tunnel worker error: {e}")
                break

        logger.info("Tunnel worker stopped")

    def _forward_connection(self, client_socket: socket.socket,
                          channel: paramiko.Channel) -> None:
        """
        Forward data between client socket and SSH channel

        Args:
            client_socket: Local client socket
            channel: SSH channel to remote host
        """
        def forward_data(source, destination, direction: str):
            """Forward data from source to destination"""
            try:
                while True:
                    data = source.recv(4096)
                    if not data:
                        break
                    destination.sendall(data)
            except Exception as e:
                if not self._stop_tunnel.is_set():
                    logger.debug(f"Forwarding error ({direction}): {e}")
            finally:
                try:
                    source.close()
                    destination.close()
                except Exception:
                    pass

        # Create bidirectional forwarding threads
        client_to_remote = threading.Thread(
            target=forward_data,
            args=(client_socket, channel, "client->remote"),
            daemon=True
        )
        remote_to_client = threading.Thread(
            target=forward_data,
            args=(channel, client_socket, "remote->client"),
            daemon=True
        )

        client_to_remote.start()
        remote_to_client.start()

        # Wait for both directions to complete
        client_to_remote.join()
        remote_to_client.join()

    def _cleanup(self) -> None:
        """Cleanup all resources"""
        # Close server socket
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
            self._server_socket = None

        # Close SSH connection
        if self._ssh_client:
            try:
                self._ssh_client.close()
            except Exception:
                pass
            self._ssh_client = None
            self._transport = None

    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()

    def __del__(self):
        """Destructor to ensure cleanup"""
        if hasattr(self, '_tunnel_active') and self._tunnel_active:
            self.stop()


def create_tunnel_from_env(config_prefix: str = 'SSH') -> Optional[SSHTunnelManager]:
    """
    Create SSH tunnel manager from environment variables

    Args:
        config_prefix: Prefix for environment variables (default: 'SSH')

    Returns:
        SSHTunnelManager instance or None if tunnel not enabled

    Environment Variables:
        USE_SSH_TUNNEL: Enable/disable tunnel (true/false)
        SSH_GATEWAY_HOST: Gateway host
        SSH_GATEWAY_PORT: Gateway SSH port (default: 22)
        SSH_GATEWAY_USER: Gateway SSH user (default: root)
        SSH_KEY_FILE: Path to private key
        REMOTE_POSTGRES_HOST: Remote DB host (default: db)
        REMOTE_POSTGRES_PORT: Remote DB port (default: 5438)
        LOCAL_remote_POSTGRES_PORT: Local bind port (default: 5439)
    """
    # Check if tunnel is enabled
    use_tunnel = os.getenv('USE_SSH_TUNNEL', 'false').lower() in ('true', '1', 'yes')
    if not use_tunnel:
        return None

    # Get tunnel configuration
    gateway_host = os.getenv(f'{config_prefix}_GATEWAY_HOST')
    if not gateway_host:
        logger.error(f"{config_prefix}_GATEWAY_HOST not configured")
        return None

    gateway_port = int(os.getenv(f'{config_prefix}_GATEWAY_PORT', '22'))
    gateway_user = os.getenv(f'{config_prefix}_GATEWAY_USER', 'root')
    key_file = os.getenv(f'{config_prefix}_KEY_FILE')

    remote_host = os.getenv('REMOTE_POSTGRES_HOST', 'db')
    remote_port = int(os.getenv('REMOTE_POSTGRES_PORT', '5438'))
    local_port = int(os.getenv('LOCAL_remote_POSTGRES_PORT', '5439'))

    return SSHTunnelManager(
        gateway_host=gateway_host,
        gateway_port=gateway_port,
        gateway_user=gateway_user,
        key_file=key_file,
        remote_host=remote_host,
        remote_port=remote_port,
        local_port=local_port
    )