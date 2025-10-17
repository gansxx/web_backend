#!/usr/bin/env python3
"""
R2 Package Management Interactive CLI Tool

A user-friendly terminal interface for managing R2 packages.
Supports all R2 API operations with colorful menus and formatted output.

Usage:
    python scripts/r2_cli.py
    python scripts/r2_cli.py --base-url http://localhost:8001
    python scripts/r2_cli.py --user-id "your-uuid"
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List
import json

import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from rich.syntax import Syntax


class R2Config:
    """Configuration for R2 API client"""

    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        user_id: str = "00000000-0000-0000-0000-000000000000",
        timeout: int = 30
    ):
        self.base_url = base_url.rstrip('/')
        self.user_id = user_id
        self.timeout = timeout

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables"""
        return cls(
            base_url=os.getenv('R2_API_URL', 'http://localhost:8001'),
            user_id=os.getenv('R2_USER_ID', '00000000-0000-0000-0000-000000000000'),
            timeout=int(os.getenv('R2_TIMEOUT', '30'))
        )


class R2Client:
    """R2 API Client - handles all API communications"""

    def __init__(self, config: R2Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'R2-CLI/1.0'
        })
        self.access_token: Optional[str] = None  # Store access token for authenticated requests

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and errors"""
        try:
            if response.status_code == 403:
                return {
                    'error': True,
                    'message': '🔒 访问被拒绝：此操作只能从本地主机执行',
                    'status_code': 403
                }
            elif response.status_code == 404:
                return {
                    'error': True,
                    'message': '❌ 未找到：请求的资源不存在',
                    'status_code': 404
                }
            elif response.status_code >= 400:
                error_detail = response.json().get('detail', response.text) if response.content else response.text
                return {
                    'error': True,
                    'message': f'❌ 错误 ({response.status_code}): {error_detail}',
                    'status_code': response.status_code
                }

            # Success response
            if response.content:
                return {'error': False, 'data': response.json(), 'status_code': response.status_code}
            else:
                return {'error': False, 'data': {}, 'status_code': response.status_code}

        except json.JSONDecodeError:
            return {'error': False, 'data': {'message': response.text}, 'status_code': response.status_code}
        except Exception as e:
            return {'error': True, 'message': f'❌ 处理响应时出错: {str(e)}', 'status_code': -1}

    def upload_package(
        self,
        file_path: str,
        package_name: str,
        version: str,
        description: Optional[str] = None,
        tags: Optional[str] = None,
        is_public: bool = True,
        uploader_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload a package file"""
        try:
            file_path = Path(file_path).resolve()
            if not file_path.exists():
                return {'error': True, 'message': f'❌ 文件不存在: {file_path}'}

            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f, 'application/octet-stream')}
                data = {
                    'package_name': package_name,
                    'version': version,
                    'is_public': str(is_public).lower()
                }
                if description:
                    data['description'] = description
                if tags:
                    data['tags'] = tags
                if uploader_id:
                    data['uploader_id'] = uploader_id

                response = self.session.post(
                    f'{self.config.base_url}/r2/packages/upload',
                    files=files,
                    data=data,
                    timeout=self.config.timeout * 2  # Double timeout for uploads
                )
                return self._handle_response(response)

        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}
        except Exception as e:
            return {'error': True, 'message': f'❌ 上传失败: {str(e)}'}

    def get_package_info(self, package_name: str, version: str) -> Dict[str, Any]:
        """Get detailed package information"""
        try:
            response = self.session.get(
                f'{self.config.base_url}/r2/packages/{package_name}/{version}',
                timeout=self.config.timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def list_package_versions(
        self,
        package_name: str,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List all versions of a package"""
        try:
            response = self.session.get(
                f'{self.config.base_url}/r2/packages/{package_name}/versions',
                params={'limit': limit, 'offset': offset},
                timeout=self.config.timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def search_packages(
        self,
        search_term: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_public: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search packages"""
        try:
            payload = {'limit': limit, 'offset': offset}
            if search_term:
                payload['search_term'] = search_term
            if tags:
                payload['tags'] = tags
            if is_public is not None:
                payload['is_public'] = is_public

            response = self.session.post(
                f'{self.config.base_url}/r2/packages/search',
                json=payload,
                timeout=self.config.timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def list_public_packages(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List all public packages"""
        try:
            response = self.session.get(
                f'{self.config.base_url}/r2/packages/public',
                params={'limit': limit, 'offset': offset},
                timeout=self.config.timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def list_my_uploads(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List packages uploaded by specific user"""
        try:
            uid = user_id or self.config.user_id
            response = self.session.get(
                f'{self.config.base_url}/r2/packages/my-uploads',
                params={'user_id': uid, 'limit': limit, 'offset': offset},
                timeout=self.config.timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def update_package(
        self,
        package_name: str,
        version: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_public: Optional[bool] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update package metadata"""
        try:
            payload = {}
            if description is not None:
                payload['description'] = description
            if tags is not None:
                payload['tags'] = tags
            if is_public is not None:
                payload['is_public'] = is_public
            if status is not None:
                payload['status'] = status

            response = self.session.patch(
                f'{self.config.base_url}/r2/packages/{package_name}/{version}',
                json=payload,
                timeout=self.config.timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def delete_package(
        self,
        package_name: str,
        version: str,
        hard_delete: bool = False
    ) -> Dict[str, Any]:
        """Delete package"""
        try:
            response = self.session.delete(
                f'{self.config.base_url}/r2/packages/{package_name}/{version}',
                params={'hard_delete': hard_delete},
                timeout=self.config.timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get overall storage statistics"""
        try:
            response = self.session.get(
                f'{self.config.base_url}/r2/packages/stats/storage',
                timeout=self.config.timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def get_package_stats(self, package_name: str) -> Dict[str, Any]:
        """Get statistics for specific package"""
        try:
            response = self.session.get(
                f'{self.config.base_url}/r2/packages/stats/{package_name}',
                timeout=self.config.timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def cleanup_old_packages(
        self,
        days_threshold: int = 90,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Cleanup old archived packages"""
        try:
            response = self.session.post(
                f'{self.config.base_url}/r2/packages/cleanup',
                json={'days_threshold': days_threshold, 'dry_run': dry_run},
                timeout=self.config.timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def verify_package_integrity(self, package_name: str, version: str) -> Dict[str, Any]:
        """Verify package file integrity"""
        try:
            response = self.session.get(
                f'{self.config.base_url}/r2/packages/{package_name}/{version}/verify',
                timeout=self.config.timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def health_check(self) -> Dict[str, Any]:
        """Check R2 and database connectivity"""
        try:
            response = self.session.get(
                f'{self.config.base_url}/r2/packages/health',
                timeout=self.config.timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def generate_download_url(
        self,
        package_name: str,
        version: str,
        expiration: int = 3600,
        use_public_domain: bool = True,
        authenticated: bool = False
    ) -> Dict[str, Any]:
        """
        Generate download URL for package

        Args:
            package_name: Package name
            version: Package version
            expiration: URL expiration in seconds
            use_public_domain: Use public domain for URL
            authenticated: Whether to use authentication (for private packages)

        Returns:
            Dict with download_url and metadata
        """
        try:
            headers = {}
            if authenticated and self.access_token:
                headers['Authorization'] = f'Bearer {self.access_token}'

            response = self.session.get(
                f'{self.config.base_url}/r2/packages/{package_name}/{version}/download',
                params={'expiration': expiration, 'use_public_domain': use_public_domain},
                headers=headers,
                timeout=self.config.timeout
            )
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Login with email and password to access private packages

        Args:
            email: User email
            password: User password

        Returns:
            Dict with access_token or error
        """
        try:
            response = self.session.post(
                f'{self.config.base_url}/login',
                json={'email': email, 'password': password},
                timeout=self.config.timeout
            )

            result = self._handle_response(response)

            if not result.get('error'):
                data = result.get('data', {})
                self.access_token = data.get('access_token')
                if self.access_token:
                    # Get user info to retrieve UUID
                    user_info = self.get_current_user()

                    if not user_info.get('error'):
                        user_data = user_info.get('data', {})
                        user_uuid = user_data.get('id')

                        if user_uuid:
                            # Store UUID globally to replace default
                            self.config.user_id = user_uuid
                            result['user_id'] = user_uuid
                            result['message'] = f'✅ 登录成功! 用户 ID: {user_uuid[:8]}...'
                        else:
                            result['message'] = '✅ 登录成功! (未获取到用户ID)'
                    else:
                        # Login succeeded but failed to get user info
                        result['message'] = '✅ 登录成功! (获取用户信息失败)'
                else:
                    result['error'] = True
                    result['message'] = '❌ 登录失败：未获取到访问令牌'

            return result
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def get_current_user(self) -> Dict[str, Any]:
        """
        Get current authenticated user information

        Requires authentication (access_token must be set)

        Returns:
            Dict with user info including UUID (id field)
        """
        try:
            if not self.access_token:
                return {'error': True, 'message': '❌ 未登录，无法获取用户信息'}

            headers = {'Authorization': f'Bearer {self.access_token}'}

            response = self.session.get(
                f'{self.config.base_url}/me',
                headers=headers,
                timeout=self.config.timeout
            )

            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            return {'error': True, 'message': f'❌ 网络错误: {str(e)}'}

    def is_authenticated(self) -> bool:
        """Check if client is authenticated"""
        return self.access_token is not None


class R2CLI:
    """Interactive CLI for R2 Package Management"""

    def __init__(self, client: R2Client):
        self.client = client
        self.console = Console()

    def show_banner(self):
        """Display welcome banner"""
        banner = """
╔═══════════════════════════════════════════════════╗
║   🚀 R2 包管理系统 - 交互式终端工具 v1.0         ║
║                                                   ║
║   📦 完整的包管理功能                             ║
║   🎨 美观的终端界面                               ║
║   ⚡ 快速且易用                                   ║
╚═══════════════════════════════════════════════════╝
        """
        self.console.print(banner, style="bold cyan")
        self.console.print(f"API 地址: {self.client.config.base_url}", style="dim")

        # Show authentication status
        if self.client.is_authenticated():
            user_id = self.client.config.user_id
            # Check if using default system UUID
            if user_id == "00000000-0000-0000-0000-000000000000":
                self.console.print("🔓 状态: 已登录 (可访问私有包)", style="green")
                self.console.print("⚠️  用户 ID: 系统默认 (建议重新登录获取)", style="yellow dim")
            else:
                self.console.print("🔓 状态: 已登录 (可访问私有包)", style="green")
                self.console.print(f"🆔 用户 ID: {user_id[:8]}...{user_id[-4:]}", style="cyan dim")
        else:
            self.console.print("🔒 状态: 未登录 (仅可访问公开包)", style="yellow")

        self.console.print()

    def show_menu(self) -> str:
        """Display main menu and get user choice"""
        menu_items = [
            ("1", "📤", "上传包"),
            ("2", "📊", "查看包信息"),
            ("3", "📋", "列出包版本"),
            ("4", "🔍", "搜索包"),
            ("5", "📚", "列出所有公开包"),
            ("6", "👤", "查看我的上传"),
            ("7", "✏️", "更新包元数据"),
            ("8", "🗑️", "删除包"),
            ("9", "📈", "查看存储统计"),
            ("10", "📊", "查看包统计"),
            ("11", "🧹", "清理旧包"),
            ("12", "✅", "验证包完整性"),
            ("13", "💚", "健康检查"),
            ("14", "📥", "生成下载链接"),
            ("15", "🔐", "登录账号"),
            ("16", "🔒", "下载私有包"),
            ("0", "🚪", "退出"),
        ]

        table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
        table.add_column("选项", style="cyan bold", width=6)
        table.add_column("图标", width=4)
        table.add_column("操作", style="white")

        for num, icon, desc in menu_items:
            table.add_row(num, icon, desc)

        self.console.print(table)
        return Prompt.ask("\n选择操作", default="0")

    def format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def display_result(self, result: Dict[str, Any], title: str = "结果"):
        """Display API result in formatted way"""
        if result.get('error'):
            self.console.print(f"\n{result.get('message', '未知错误')}", style="bold red")
            return

        data = result.get('data', {})

        if not data:
            self.console.print("\n✅ 操作成功!", style="bold green")
            return

        # Display as formatted JSON for complex data
        if isinstance(data, dict) and len(data) > 0:
            syntax = Syntax(json.dumps(data, indent=2, ensure_ascii=False), "json", theme="monokai", line_numbers=False)
            panel = Panel(syntax, title=f"✅ {title}", border_style="green")
            self.console.print(panel)
        else:
            self.console.print(f"\n✅ {title}", style="bold green")
            self.console.print(data)

    def display_table(self, data: List[Dict], columns: List[tuple], title: str = "结果", field_map: Optional[Dict[str, str]] = None):
        """
        Display data in table format

        Args:
            data: List of data dictionaries
            columns: List of (display_name, style) tuples
            title: Table title
            field_map: Optional mapping of display_name -> data_field_name
                       If provided, uses mapped field names for data lookup
                       If not provided, uses display name transformation (backwards compatible)
        """
        if not data:
            self.console.print("\n📭 没有找到数据", style="yellow")
            return

        table = Table(title=title, box=box.ROUNDED, show_lines=False)

        # Add columns
        for col_name, col_style in columns:
            table.add_column(col_name, style=col_style)

        # Add rows
        for item in data:
            row = []
            for col_name, _ in columns:
                # Get the actual field name to lookup
                if field_map and col_name in field_map:
                    # Use explicit field mapping
                    field_name = field_map[col_name]
                    value = item.get(field_name, '')
                else:
                    # Fall back to original behavior: transform display name
                    value = item
                    for key in col_name.lower().replace(' ', '_').split('.'):
                        value = value.get(key, '')
                        if not isinstance(value, dict):
                            break

                # Format special values
                if 'size' in col_name.lower() and isinstance(value, int):
                    value = self.format_size(value)
                elif isinstance(value, list):
                    value = ', '.join(str(v) for v in value)
                elif isinstance(value, dict):
                    value = json.dumps(value, ensure_ascii=False)

                row.append(str(value))

            table.add_row(*row)

        self.console.print(table)

    def handle_upload(self):
        """Handle package upload"""
        self.console.print("\n📤 上传包", style="bold cyan")
        self.console.print()

        package_name = Prompt.ask("包名称")
        version = Prompt.ask("版本号 (如: 1.0.0)")
        file_path = Prompt.ask("文件路径")
        description = Prompt.ask("描述 (可选)", default="")
        tags = Prompt.ask("标签 (逗号分隔, 可选)", default="")
        is_public = Confirm.ask("是否公开?", default=True)

        # Show current user_id from config
        self.console.print(f"\n📋 将使用用户 ID: {self.client.config.user_id}", style="dim")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("⏳ 正在上传...", total=None)
            result = self.client.upload_package(
                file_path=file_path,
                package_name=package_name,
                version=version,
                description=description if description else None,
                tags=tags if tags else None,
                is_public=is_public,
                uploader_id=self.client.config.user_id  # Pass user_id from config
            )
            progress.stop()

        self.display_result(result, "上传成功")

    def handle_get_package_info(self):
        """Handle get package info"""
        self.console.print("\n📊 查看包信息", style="bold cyan")
        self.console.print()

        package_name = Prompt.ask("包名称")
        version = Prompt.ask("版本号")

        result = self.client.get_package_info(package_name, version)
        self.display_result(result, f"{package_name} v{version} 信息")

    def handle_list_versions(self):
        """Handle list package versions"""
        self.console.print("\n📋 列出包版本", style="bold cyan")
        self.console.print()

        package_name = Prompt.ask("包名称")
        limit = int(Prompt.ask("最大显示数量", default="20"))

        result = self.client.list_package_versions(package_name, limit=limit)

        if result.get('error'):
            self.display_result(result)
        else:
            data = result.get('data', {})
            versions = data.get('versions', [])
            if versions:
                columns = [
                    ("版本", "cyan"),
                    ("状态", "green"),
                    ("下载次数", "yellow"),
                    ("创建时间", "blue")
                ]
                field_map = {
                    "版本": "version",
                    "状态": "status",
                    "下载次数": "download_count",
                    "创建时间": "created_at"
                }
                self.display_table(versions, columns, f"{package_name} 的所有版本", field_map=field_map)
            else:
                self.console.print("\n📭 没有找到版本", style="yellow")

    def handle_search(self):
        """Handle search packages"""
        self.console.print("\n🔍 搜索包", style="bold cyan")
        self.console.print()

        search_term = Prompt.ask("搜索关键词 (可选)", default="")
        tags_input = Prompt.ask("标签 (逗号分隔, 可选)", default="")
        is_public = Confirm.ask("只搜索公开包?", default=True)
        limit = int(Prompt.ask("最大显示数量", default="20"))

        tags = [t.strip() for t in tags_input.split(',')] if tags_input else None

        result = self.client.search_packages(
            search_term=search_term if search_term else None,
            tags=tags,
            is_public=is_public,
            limit=limit
        )

        if result.get('error'):
            self.display_result(result)
        else:
            data = result.get('data', {})
            packages = data.get('results', [])
            if packages:
                columns = [
                    ("包名", "cyan bold"),
                    ("版本", "green"),
                    ("描述", "white"),
                    ("下载次数", "yellow")
                ]
                field_map = {
                    "包名": "package_name",
                    "版本": "version",
                    "描述": "description",
                    "下载次数": "download_count"
                }
                self.display_table(packages, columns, f"找到 {len(packages)} 个包", field_map=field_map)
            else:
                self.console.print("\n📭 没有找到匹配的包", style="yellow")

    def handle_list_public(self):
        """Handle list public packages"""
        self.console.print("\n📚 列出所有公开包", style="bold cyan")
        self.console.print()

        limit = int(Prompt.ask("最大显示数量", default="20"))

        result = self.client.list_public_packages(limit=limit)

        if result.get('error'):
            self.display_result(result)
        else:
            data = result.get('data', {})
            packages = data.get('results', [])
            if packages:
                columns = [
                    ("包名", "cyan bold"),
                    ("版本", "green"),
                    ("描述", "white"),
                    ("下载次数", "yellow")
                ]
                field_map = {
                    "包名": "package_name",
                    "版本": "version",
                    "描述": "description",
                    "下载次数": "download_count"
                }
                self.display_table(packages, columns, f"公开包列表 (共 {len(packages)} 个)", field_map=field_map)
            else:
                self.console.print("\n📭 没有公开包", style="yellow")

    def handle_my_uploads(self):
        """Handle list my uploads"""
        self.console.print("\n👤 查看我的上传", style="bold cyan")
        self.console.print()

        user_id = Prompt.ask("用户 ID", default=self.client.config.user_id)
        limit = int(Prompt.ask("最大显示数量", default="20"))

        result = self.client.list_my_uploads(user_id=user_id, limit=limit)

        if result.get('error'):
            self.display_result(result)
        else:
            data = result.get('data', {})
            packages = data.get('packages', [])
            if packages:
                columns = [
                    ("包名", "cyan bold"),
                    ("版本", "green"),
                    ("状态", "yellow"),
                    ("下载次数", "blue")
                ]
                field_map = {
                    "包名": "package_name",
                    "版本": "version",
                    "状态": "status",
                    "下载次数": "download_count"
                }
                self.display_table(packages, columns, f"我的上传 (共 {len(packages)} 个)", field_map=field_map)
            else:
                self.console.print("\n📭 您还没有上传任何包", style="yellow")

    def handle_update(self):
        """Handle update package"""
        self.console.print("\n✏️ 更新包元数据", style="bold cyan")
        self.console.print()

        package_name = Prompt.ask("包名称")
        version = Prompt.ask("版本号")

        self.console.print("\n请输入要更新的字段 (留空则不更新):")
        description = Prompt.ask("新描述", default="")
        tags_input = Prompt.ask("新标签 (逗号分隔)", default="")
        is_public_input = Prompt.ask("是否公开 (y/n/留空)", default="")

        tags = [t.strip() for t in tags_input.split(',')] if tags_input else None
        is_public = None
        if is_public_input.lower() == 'y':
            is_public = True
        elif is_public_input.lower() == 'n':
            is_public = False

        if not any([description, tags, is_public is not None]):
            self.console.print("\n⚠️ 没有提供任何更新内容", style="yellow")
            return

        result = self.client.update_package(
            package_name=package_name,
            version=version,
            description=description if description else None,
            tags=tags,
            is_public=is_public
        )

        self.display_result(result, "更新成功")

    def handle_delete(self):
        """Handle delete package"""
        self.console.print("\n🗑️ 删除包", style="bold red")
        self.console.print()

        package_name = Prompt.ask("包名称")
        version = Prompt.ask("版本号")
        hard_delete = Confirm.ask("永久删除 (硬删除)? 否则为软删除", default=False)

        if not Confirm.ask(f"⚠️ 确认删除 {package_name} v{version}?", default=False):
            self.console.print("\n❌ 已取消删除", style="yellow")
            return

        result = self.client.delete_package(package_name, version, hard_delete=hard_delete)
        self.display_result(result, "删除成功")

    def handle_storage_stats(self):
        """Handle get storage stats"""
        self.console.print("\n📈 查看存储统计", style="bold cyan")
        self.console.print()

        result = self.client.get_storage_stats()
        self.display_result(result, "存储统计")

    def handle_package_stats(self):
        """Handle get package stats"""
        self.console.print("\n📊 查看包统计", style="bold cyan")
        self.console.print()

        package_name = Prompt.ask("包名称")

        result = self.client.get_package_stats(package_name)
        self.display_result(result, f"{package_name} 统计信息")

    def handle_cleanup(self):
        """Handle cleanup old packages"""
        self.console.print("\n🧹 清理旧包", style="bold cyan")
        self.console.print()

        days = int(Prompt.ask("归档天数阈值", default="90"))
        dry_run = Confirm.ask("仅预览 (不实际删除)?", default=True)

        result = self.client.cleanup_old_packages(days_threshold=days, dry_run=dry_run)

        if result.get('error'):
            self.display_result(result)
        else:
            data = result.get('data', {})
            packages = data.get('packages', [])
            marked = data.get('packages_marked', 0)

            self.console.print(f"\n{'[预览模式]' if dry_run else '[执行模式]'}", style="bold yellow")
            self.console.print(f"找到 {marked} 个符合条件的包\n")

            if packages:
                columns = [
                    ("包名", "cyan"),
                    ("版本", "green"),
                    ("归档时间", "yellow")
                ]
                field_map = {
                    "包名": "package_name",
                    "版本": "version",
                    "归档时间": "updated_at"
                }
                self.display_table(packages, columns, "待清理的包", field_map=field_map)

    def handle_verify(self):
        """Handle verify package integrity"""
        self.console.print("\n✅ 验证包完整性", style="bold cyan")
        self.console.print()

        package_name = Prompt.ask("包名称")
        version = Prompt.ask("版本号")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("⏳ 正在验证...", total=None)
            result = self.client.verify_package_integrity(package_name, version)
            progress.stop()

        if result.get('error'):
            self.display_result(result)
        else:
            data = result.get('data', {})
            verified = data.get('integrity_verified', False)

            if verified:
                self.console.print(f"\n✅ {package_name} v{version} 完整性验证通过!", style="bold green")
            else:
                self.console.print(f"\n❌ {package_name} v{version} 完整性验证失败!", style="bold red")

    def handle_health(self):
        """Handle health check"""
        self.console.print("\n💚 健康检查", style="bold cyan")
        self.console.print()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("⏳ 检查中...", total=None)
            result = self.client.health_check()
            progress.stop()

        if result.get('error'):
            self.display_result(result)
        else:
            data = result.get('data', {})
            status = data.get('status', 'unknown')
            r2_ok = data.get('r2_connection', False)
            db_ok = data.get('database_connection', False)

            self.console.print(f"\n状态: {status}", style="bold")
            self.console.print(f"R2 连接: {'✅ 正常' if r2_ok else '❌ 异常'}")
            self.console.print(f"数据库连接: {'✅ 正常' if db_ok else '❌ 异常'}")

    def handle_download_url(self):
        """Handle generate download URL"""
        self.console.print("\n📥 生成下载链接", style="bold cyan")
        self.console.print()

        package_name = Prompt.ask("包名称")
        version = Prompt.ask("版本号")
        expiration = int(Prompt.ask("链接有效期 (秒)", default="3600"))

        result = self.client.generate_download_url(
            package_name=package_name,
            version=version,
            expiration=expiration
        )

        if result.get('error'):
            self.display_result(result)
        else:
            data = result.get('data', {})
            url = data.get('download_url', '')
            expires_in = data.get('expires_in', 0)

            self.console.print(f"\n✅ 下载链接已生成!", style="bold green")
            self.console.print(f"\n🔗 下载链接:\n{url}", style="cyan")
            self.console.print(f"\n⏰ 有效期: {expires_in} 秒 ({expires_in // 60} 分钟)", style="yellow")

    def handle_login(self):
        """Handle user login"""
        self.console.print("\n🔐 登录账号", style="bold cyan")
        self.console.print()

        if self.client.is_authenticated():
            self.console.print("✅ 您已经登录!", style="green")
            return

        email = Prompt.ask("邮箱")
        password = Prompt.ask("密码", password=True)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("⏳ 登录中...", total=None)
            result = self.client.login(email, password)
            progress.stop()

        if result.get('error'):
            self.console.print(f"\n❌ 登录失败: {result.get('message', '未知错误')}", style="bold red")
        else:
            data = result.get('data', {})
            user_id = result.get('user_id') or data.get('id')

            self.console.print(f"\n✅ 登录成功!", style="bold green")

            if user_id:
                # Show full UUID
                self.console.print(f"🆔 用户 ID: {user_id}", style="cyan")
                self.console.print(f"📝 所有上传将使用此用户 ID", style="dim")

            self.console.print("🔓 您现在可以访问私有包了!", style="green")

    def handle_private_download(self):
        """Handle private package download"""
        self.console.print("\n🔒 下载私有包", style="bold cyan")
        self.console.print()

        if not self.client.is_authenticated():
            self.console.print("❌ 您尚未登录！请先使用菜单选项 15 登录账号。", style="bold red")
            return

        package_name = Prompt.ask("包名称")
        version = Prompt.ask("版本号")
        expiration = int(Prompt.ask("链接有效期 (秒)", default="3600"))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("⏳ 正在生成下载链接...", total=None)
            result = self.client.generate_download_url(
                package_name=package_name,
                version=version,
                expiration=expiration,
                authenticated=True  # Use authentication for private packages
            )
            progress.stop()

        if result.get('error'):
            error_msg = result.get('message', '未知错误')
            if '401' in str(error_msg) or 'Authentication' in str(error_msg):
                self.console.print(f"\n❌ 需要登录才能访问此私有包", style="bold red")
                self.console.print("请先使用菜单选项 15 登录账号", style="yellow")
            else:
                self.console.print(f"\n❌ 获取下载链接失败: {error_msg}", style="bold red")
        else:
            data = result.get('data', {})
            url = data.get('download_url', '')
            expires_in = data.get('expires_in', 0)

            self.console.print(f"\n✅ 私有包下载链接已生成!", style="bold green")
            self.console.print(f"\n🔗 下载链接:\n{url}", style="cyan")
            self.console.print(f"\n⏰ 有效期: {expires_in} 秒 ({expires_in // 60} 分钟)", style="yellow")

    def run(self):
        """Main CLI loop"""
        self.show_banner()

        handlers = {
            '1': self.handle_upload,
            '2': self.handle_get_package_info,
            '3': self.handle_list_versions,
            '4': self.handle_search,
            '5': self.handle_list_public,
            '6': self.handle_my_uploads,
            '7': self.handle_update,
            '8': self.handle_delete,
            '9': self.handle_storage_stats,
            '10': self.handle_package_stats,
            '11': self.handle_cleanup,
            '12': self.handle_verify,
            '13': self.handle_health,
            '14': self.handle_download_url,
            '15': self.handle_login,
            '16': self.handle_private_download,
        }

        while True:
            try:
                choice = self.show_menu()

                if choice == '0':
                    self.console.print("\n👋 再见!", style="bold cyan")
                    break

                handler = handlers.get(choice)
                if handler:
                    handler()
                else:
                    self.console.print(f"\n❌ 无效选项: {choice}", style="bold red")

                self.console.print("\n" + "=" * 60)
                Prompt.ask("\n按 Enter 继续", default="")
                self.console.clear()
                self.show_banner()

            except KeyboardInterrupt:
                self.console.print("\n\n👋 再见!", style="bold cyan")
                break
            except Exception as e:
                self.console.print(f"\n❌ 发生错误: {str(e)}", style="bold red")
                self.console.print("\n按 Enter 继续...")
                input()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='R2 Package Management Interactive CLI Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s
  %(prog)s --base-url http://localhost:8001
  %(prog)s --user-id "your-uuid-here"
  %(prog)s --base-url http://localhost:8001 --user-id "uuid" --timeout 60

环境变量:
  R2_API_URL     - API 基础 URL (默认: http://localhost:8001)
  R2_USER_ID     - 默认用户 ID (默认: 00000000-0000-0000-0000-000000000000)
  R2_TIMEOUT     - 请求超时时间秒数 (默认: 30)
        """
    )

    parser.add_argument(
        '--base-url',
        help='API base URL (default: http://localhost:8001)',
        default=None
    )
    parser.add_argument(
        '--user-id',
        help='Default user ID for operations',
        default=None
    )
    parser.add_argument(
        '--timeout',
        type=int,
        help='Request timeout in seconds (default: 30)',
        default=None
    )

    args = parser.parse_args()

    # Load config from environment, then override with CLI args
    config = R2Config.from_env()

    if args.base_url:
        config.base_url = args.base_url
    if args.user_id:
        config.user_id = args.user_id
    if args.timeout:
        config.timeout = args.timeout

    # Create client and CLI
    client = R2Client(config)
    cli = R2CLI(client)

    # Run the CLI
    try:
        cli.run()
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
