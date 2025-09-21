import pytest
import os
from unittest.mock import patch, MagicMock, Mock
from supabase import Client
import sys

# 添加父级目录到 Python 路径以便导入模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from spdb_init import spdbConfig


class TestSpdbConfig:
    """Supabase 数据库配置类的测试"""

    @pytest.fixture
    def mock_env_vars(self):
        """Mock 环境变量"""
        with patch.dict(os.environ, {
            'SUPABASE_URL': 'http://test.supabase.co',
            'SERVICE_ROLE_KEY': 'test_key_123'
        }):
            yield

    @pytest.fixture
    def mock_supabase_client(self):
        """Mock Supabase 客户端"""
        with patch('spdb_init.create_client') as mock_create_client:
            mock_client = Mock(spec=Client)
            mock_create_client.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def spdb_config(self, mock_env_vars, mock_supabase_client):
        """创建 spdbConfig 实例"""
        return spdbConfig()

    def test_init_with_env_vars(self, mock_env_vars, mock_supabase_client):
        """测试使用环境变量初始化"""
        config = spdbConfig()
        
        assert config.url == 'http://test.supabase.co'
        assert config.key == 'test_key_123'
        assert config.supabase is not None

    def test_init_with_default_values(self, mock_supabase_client):
        """测试使用默认值初始化"""
        with patch.dict(os.environ, {}, clear=True):
            config = spdbConfig()
            
            assert config.url == 'http://localhost:8000'
            assert config.key == 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE'

    def test_init_table_success(self, spdb_config, mock_supabase_client):
        """测试成功创建表"""
        # Mock RPC 调用的返回值
        mock_response = Mock()
        mock_response.execute.return_value = Mock()
        mock_supabase_client.rpc.return_value = mock_response
        
        # 调用 init_table 方法
        spdb_config.init_table()
        
        # 验证 RPC 调用次数和参数
        assert mock_supabase_client.rpc.call_count == 2
        
        # 验证第一次调用（创建 schema）
        first_call = mock_supabase_client.rpc.call_args_list[0]
        assert first_call[0][0] == "exec_sql"
        # 检查参数格式，可能是位置参数或关键字参数
        if len(first_call[0]) > 1:
            # 位置参数
            assert "CREATE SCHEMA IF NOT EXISTS self_web_vpn" in first_call[0][1]["query"]
        else:
            # 关键字参数
            assert "CREATE SCHEMA IF NOT EXISTS self_web_vpn" in first_call[1]["query"]
        
        # 验证第二次调用（创建表）
        second_call = mock_supabase_client.rpc.call_args_list[1]
        assert second_call[0][0] == "exec_sql"
        if len(second_call[0]) > 1:
            assert "create table IF NOT EXISTS self_web_vpn.products" in second_call[0][1]["query"]
        else:
            assert "create table IF NOT EXISTS self_web_vpn.products" in second_call[1]["query"]

    def test_init_table_failure(self, spdb_config, mock_supabase_client):
        """测试创建表失败的情况"""
        # Mock RPC 调用抛出异常
        mock_supabase_client.rpc.side_effect = Exception("Database connection failed")
        
        # 验证异常被抛出
        with pytest.raises(Exception, match="Database connection failed"):
            spdb_config.init_table()

    def test_insert_data_success(self, spdb_config, mock_supabase_client):
        """测试成功插入数据"""
        # Mock RPC 调用的返回值
        mock_response = Mock()
        mock_response.execute.return_value = Mock()
        mock_supabase_client.rpc.return_value = mock_response
        
        # 调用 insert_data 方法
        spdb_config.insert_data(
            product_name="Test VPN",
            subscription_url="https://test.com/subscribe",
            email="test@example.com",
            phone="1234567890",
            duration_days=30
        )
        
        # 验证 RPC 调用
        mock_supabase_client.rpc.assert_called_once()
        call_args = mock_supabase_client.rpc.call_args
        
        assert call_args[0][0] == "exec_sql"
        # 检查参数格式
        if len(call_args[0]) > 1:
            query = call_args[0][1]["query"]
        else:
            query = call_args[1]["query"]
        assert "INSERT INTO self_web_vpn.products" in query
        assert "Test VPN" in query
        assert "test@example.com" in query
        assert "1234567890" in query
        assert "interval '30 days'" in query

    def test_insert_data_with_default_duration(self, spdb_config, mock_supabase_client):
        """测试使用默认持续时间插入数据"""
        mock_response = Mock()
        mock_response.execute.return_value = Mock()
        mock_supabase_client.rpc.return_value = mock_response
        
        spdb_config.insert_data(
            product_name="Default VPN",
            subscription_url="https://default.com",
            email="default@example.com",
            phone="9876543210"
        )
        
        call_args = mock_supabase_client.rpc.call_args
        if len(call_args[0]) > 1:
            query = call_args[0][1]["query"]
        else:
            query = call_args[1]["query"]
        assert "interval '365 days'" in query

    def test_insert_data_failure(self, spdb_config, mock_supabase_client):
        """测试插入数据失败的情况"""
        mock_supabase_client.rpc.side_effect = Exception("Insert failed")
        
        with pytest.raises(Exception, match="Insert failed"):
            spdb_config.insert_data(
                product_name="Failed VPN",
                subscription_url="https://failed.com",
                email="failed@example.com",
                phone="0000000000"
            )

    def test_fetch_data_user_success(self, spdb_config, mock_supabase_client):
        """测试成功获取用户数据"""
        # Mock 返回数据
        mock_data = [
            {
                'id': 'test-uuid',
                'product_name': 'Test VPN',
                'subscription_url': 'https://test.com',
                'email': 'test@example.com',
                'phone': '1234567890'
            }
        ]
        mock_response = Mock()
        mock_response.execute.return_value = Mock()
        mock_response.execute.return_value.data = mock_data
        mock_supabase_client.rpc.return_value = mock_response
        
        # 调用 fetch_data_user 方法
        result = spdb_config.fetch_data_user()
        
        # 验证返回结果
        assert result == mock_data
        
        # 验证 RPC 调用
        mock_supabase_client.rpc.assert_called_once_with(
            "exec_sql", 
            {"query": "\n            SELECT * FROM self_web_vpn.products\n            WHERE email = auth.email();\n        "}
        )

    def test_fetch_data_user_empty_result(self, spdb_config, mock_supabase_client):
        """测试获取用户数据返回空结果"""
        mock_response = Mock()
        mock_response.execute.return_value = Mock()
        mock_response.execute.return_value.data = []
        mock_supabase_client.rpc.return_value = mock_response
        
        result = spdb_config.fetch_data_user()
        
        assert result == []

    def test_fetch_data_user_failure(self, spdb_config, mock_supabase_client):
        """测试获取用户数据失败的情况"""
        mock_supabase_client.rpc.side_effect = Exception("Query failed")
        
        with pytest.raises(Exception, match="Query failed"):
            spdb_config.fetch_data_user()

    @patch('spdb_init.logger')
    def test_logging_in_init_table(self, mock_logger, spdb_config, mock_supabase_client):
        """测试 init_table 方法的日志记录"""
        mock_response = Mock()
        mock_response.execute.return_value = Mock()
        mock_supabase_client.rpc.return_value = mock_response
        
        spdb_config.init_table()
        
        mock_logger.info.assert_called_with("Initialized self_web_vpn.products table")

    @patch('spdb_init.logger')
    def test_logging_in_insert_data(self, mock_logger, spdb_config, mock_supabase_client):
        """测试 insert_data 方法的日志记录"""
        mock_response = Mock()
        mock_response.execute.return_value = Mock()
        mock_supabase_client.rpc.return_value = mock_response
        
        spdb_config.insert_data(
            product_name="Test VPN",
            subscription_url="https://test.com",
            email="test@example.com",
            phone="1234567890"
        )
        
        mock_logger.info.assert_called_with("Inserted product Test VPN for test@example.com")


class TestSpdbConfigIntegration:
    """集成测试类"""

    @pytest.fixture
    def config_with_real_client(self):
        """使用真实客户端的配置（用于集成测试）"""
        with patch.dict(os.environ, {
            'SUPABASE_URL': 'http://localhost:8000',
            'SERVICE_ROLE_KEY': 'test_key'
        }):
            # 这里我们仍然使用 mock，但在真实的集成测试环境中可以使用真实的客户端
            with patch('spdb_init.create_client') as mock_create_client:
                mock_client = Mock(spec=Client)
                mock_create_client.return_value = mock_client
                yield spdbConfig(), mock_client

    def test_full_workflow(self, config_with_real_client):
        """测试完整的工作流程：初始化 -> 创建表 -> 插入数据 -> 查询数据"""
        config, mock_client = config_with_real_client
        
        # Mock 所有响应
        mock_response = Mock()
        mock_response.execute.return_value = Mock()
        mock_response.execute.return_value.data = [{'id': 'test', 'product_name': 'VPN'}]
        mock_client.rpc.return_value = mock_response
        
        # 执行完整流程
        config.init_table()
        config.insert_data("Test VPN", "https://test.com", "test@example.com", "1234567890")
        result = config.fetch_data_user()
        
        # 验证调用次数（init_table 调用2次，insert_data 1次，fetch_data_user 1次）
        assert mock_client.rpc.call_count == 4
        assert result == [{'id': 'test', 'product_name': 'VPN'}]


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])