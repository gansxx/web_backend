"""
SSH Management Module

Extracted SSH functionality for universal use across all VPS providers.
"""

import time
import shlex
import paramiko
from loguru import logger
from pathlib import Path
from typing import Optional, Tuple, Any
from contextlib import contextmanager

from .exceptions import VPSConnectionError


class SSHManager:
    """
    SSH connection and command execution manager
    """

    def __init__(self, hostname: str, port: int = 22, username: str = 'root',
                 key_file: Optional[str] = None, timeout: int = 30):
        """
        Initialize SSH manager

        Args:
            hostname: Remote hostname or IP address
            port: SSH port (default: 22)
            username: SSH username (default: 'root')
            key_file: Path to private key file
            timeout: Connection timeout in seconds
        """
        self.hostname = hostname
        self.port = port
        self.username = username
        self.key_file = key_file
        self.timeout = timeout
        self._ssh_client: Optional[paramiko.SSHClient] = None
        self._connected = False

    def connect(self) -> paramiko.SSHClient:
        """
        Establish SSH connection

        Returns:
            Connected Paramiko SSHClient instance

        Raises:
            VPSConnectionError: If connection fails
        """
        if self._connected and self._ssh_client:
            return self._ssh_client

        try:
            self._ssh_client = self._create_ssh_client()
            self._connected = True
            logger.info(f"SSH connection established: {self.username}@{self.hostname}:{self.port}")
            return self._ssh_client

        except Exception as e:
            self._connected = False
            self._ssh_client = None
            raise VPSConnectionError(f"Failed to connect to {self.hostname}:{self.port}: {e}")

    def disconnect(self) -> None:
        """Disconnect SSH connection"""
        if self._ssh_client and self._connected:
            try:
                self._ssh_client.close()
                logger.info(f"SSH connection closed: {self.username}@{self.hostname}:{self.port}")
            except Exception as e:
                logger.warning(f"Error closing SSH connection: {e}")
            finally:
                self._ssh_client = None
                self._connected = False

    def execute_command(self, command: str, timeout: int = 600) -> Tuple[int, str, str]:
        """
        Execute a command on the remote server

        Args:
            command: Command to execute
            timeout: Command execution timeout in seconds

        Returns:
            Tuple of (exit_status, stdout, stderr)

        Raises:
            VPSConnectionError: If SSH connection fails
        """
        if not self._connected or not self._ssh_client:
            self.connect()

        return self._execute_command_with_client(self._ssh_client, command, timeout)

    def get_sftp_client(self) -> paramiko.SFTPClient:
        """
        Get SFTP client for file operations

        Returns:
            Paramiko SFTP client instance

        Raises:
            VPSConnectionError: If SSH connection fails
        """
        if not self._connected or not self._ssh_client:
            self.connect()

        try:
            return self._ssh_client.open_sftp()
        except Exception as e:
            raise VPSConnectionError(f"Failed to open SFTP client: {e}")

    def _create_ssh_client(self) -> paramiko.SSHClient:
        """Create and configure SSH client"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        pkey = None
        if self.key_file:
            pkey = self._load_private_key(self.key_file)

        connect_kwargs = {
            'hostname': self.hostname,
            'port': int(self.port),
            'username': self.username,
            'timeout': self.timeout,
        }

        if pkey:
            logger.debug("Using parsed PKey for SSH")
            connect_kwargs['pkey'] = pkey
        elif self.key_file:
            logger.debug(f"Using key_filename for SSH: {self.key_file}")
            connect_kwargs['key_filename'] = self.key_file

        ssh.connect(**connect_kwargs)
        return ssh

    def _load_private_key(self, key_file: str) -> Optional[paramiko.PKey]:
        """
        Try to load the private key with multiple Paramiko key classes

        Args:
            key_file: Path to private key file

        Returns:
            Paramiko PKey instance on success, or None if none could be loaded
        """
        if not key_file:
            return None

        key_classes = [
            getattr(paramiko, 'RSAKey', None),
            getattr(paramiko, 'Ed25519Key', None),
            getattr(paramiko, 'ECDSAKey', None),
            getattr(paramiko, 'DSSKey', None),
        ]

        # Check if the key is in OpenSSH format
        try:
            with open(key_file, 'r', encoding='utf-8', errors='ignore') as f:
                head = f.read(512)
                if 'BEGIN OPENSSH PRIVATE KEY' in head:
                    logger.debug(f"Key {key_file} appears to be OpenSSH private key format; skip PKey parsing")
                    return None
        except Exception:
            logger.debug(f"Could not read key file header: {key_file}")

        for cls in key_classes:
            if not cls:
                continue
            try:
                return cls.from_private_key_file(key_file)
            except Exception as e:
                logger.debug(f"Key loader {cls.__name__} failed for {key_file}: {e}")

        return None

    def _execute_command_with_client(self, ssh_client: paramiko.SSHClient,
                                   command: str, timeout: int) -> Tuple[int, str, str]:
        """
        Execute command using existing SSH client

        Args:
            ssh_client: Connected Paramiko SSHClient instance
            command: Command to execute
            timeout: Command execution timeout in seconds

        Returns:
            Tuple of (exit_status, stdout, stderr)
        """
        start_ts = time.time()

        # Prepare command preview for logging
        cmd_preview = command if isinstance(command, str) else str(command)
        if len(cmd_preview) > 200:
            cmd_preview = cmd_preview[:200] + ' …(truncated)'

        host_info = self.hostname
        logger.info(f"[SSH] Exec on {host_info} -> {shlex.quote(cmd_preview)}")

        try:
            transport = ssh_client.get_transport()
            if not transport:
                raise RuntimeError("SSH transport not available")

            chan = transport.open_session()
            # Execute via bash to ensure consistency with interactive shell
            chan.exec_command(f"/bin/bash -lc {shlex.quote(command)}")
            chan.settimeout(1.0)

            stdout_buf = []
            stderr_buf = []

            while True:
                # Timeout control
                if timeout and (time.time() - start_ts) > timeout:
                    try:
                        chan.close()
                    except Exception:
                        pass
                    raise TimeoutError(f"Remote command timed out after {timeout}s")

                # Read STDOUT
                try:
                    if chan.recv_ready():
                        data = chan.recv(4096)
                        if data:
                            text = data.decode('utf-8', errors='ignore')
                            stdout_buf.append(text)
                            for line in text.splitlines():
                                logger.info(f"[SSH][STDOUT] {line}")
                except Exception:
                    pass

                # Read STDERR
                try:
                    if chan.recv_stderr_ready():
                        data_e = chan.recv_stderr(4096)
                        if data_e:
                            text_e = data_e.decode('utf-8', errors='ignore')
                            stderr_buf.append(text_e)
                            for line in text_e.splitlines():
                                logger.error(f"[SSH][STDERR] {line}")
                except Exception:
                    pass

                if chan.exit_status_ready():
                    break

                time.sleep(0.05)

            # Drain remaining data
            drain_deadline = time.time() + 1.0
            while time.time() < drain_deadline:
                drained = False
                if chan.recv_ready():
                    data = chan.recv(4096)
                    if data:
                        text = data.decode('utf-8', errors='ignore')
                        stdout_buf.append(text)
                        for line in text.splitlines():
                            logger.info(f"[SSH][STDOUT] {line}")
                        drained = True
                if chan.recv_stderr_ready():
                    data_e = chan.recv_stderr(4096)
                    if data_e:
                        text_e = data_e.decode('utf-8', errors='ignore')
                        stderr_buf.append(text_e)
                        for line in text_e.splitlines():
                            logger.error(f"[SSH][STDERR] {line}")
                        drained = True
                if not drained:
                    break

            try:
                exit_status = chan.recv_exit_status()
            except Exception:
                exit_status = 0

            out = ''.join(stdout_buf)
            err = ''.join(stderr_buf)

            duration = time.time() - start_ts
            if exit_status == 0:
                logger.info(f"[SSH] Done rc=0 in {duration:.1f}s on {host_info}")
            else:
                logger.error(f"[SSH] Failed rc={exit_status} in {duration:.1f}s on {host_info}")

            return exit_status, out, err

        except Exception as e:
            duration = time.time() - start_ts
            logger.error(f"[SSH] Exception on {host_info} after {duration:.1f}s: {e}")
            return 255, '', str(e)

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()

    def __del__(self):
        """Destructor to ensure connections are closed"""
        if hasattr(self, '_connected') and self._connected:
            self.disconnect()


@contextmanager
def ssh_connection(hostname: str, port: int = 22, username: str = 'root',
                  key_file: Optional[str] = None, timeout: int = 30):
    """
    Context manager for SSH connections

    Args:
        hostname: Remote hostname or IP address
        port: SSH port (default: 22)
        username: SSH username (default: 'root')
        key_file: Path to private key file
        timeout: Connection timeout in seconds

    Yields:
        Connected SSHManager instance
    """
    manager = SSHManager(hostname, port, username, key_file, timeout)
    try:
        manager.connect()
        yield manager
    finally:
        manager.disconnect()


# Legacy compatibility functions
def execute_remote_command(hostname: str, port: int, username: str, key_file: Optional[str],
                          command: str, timeout: int = 600) -> Tuple[int, str, str]:
    """
    Legacy function for executing remote commands

    Args:
        hostname: Remote hostname or IP address
        port: SSH port
        username: SSH username
        key_file: Path to private key file
        command: Command to execute
        timeout: Command execution timeout in seconds

    Returns:
        Tuple of (exit_status, stdout, stderr)
    """
    with ssh_connection(hostname, port, username, key_file, timeout=30) as ssh:
        return ssh.execute_command(command, timeout)


def ssh_connect(hostname: str, port: int, username: str, key_file: Optional[str],
               timeout: int = 30) -> paramiko.SSHClient:
    """
    Legacy function for creating SSH connections

    Args:
        hostname: Remote hostname or IP address
        port: SSH port
        username: SSH username
        key_file: Path to private key file
        timeout: Connection timeout in seconds

    Returns:
        Connected Paramiko SSHClient instance
    """
    manager = SSHManager(hostname, port, username, key_file, timeout)
    return manager.connect()


def execute_remote_command_with_client(ssh_client: paramiko.SSHClient, command: str,
                                     timeout: int = 600, hostname: Optional[str] = None) -> Tuple[int, str, str]:
    """
    Legacy function for executing commands with existing SSH client

    Args:
        ssh_client: Connected Paramiko SSHClient instance
        command: Command to execute
        timeout: Command execution timeout in seconds
        hostname: Hostname for logging

    Returns:
        Tuple of (exit_status, stdout, stderr)
    """
    # Create a temporary manager to use the execution logic
    temp_manager = SSHManager(hostname or "unknown")
    temp_manager._ssh_client = ssh_client
    temp_manager._connected = True

    return temp_manager._execute_command_with_client(ssh_client, command, timeout)