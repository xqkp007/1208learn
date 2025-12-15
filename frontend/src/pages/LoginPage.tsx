import React, { useState } from 'react';
import { Button, Card, Form, Input, Typography, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '@/api/client';
import { useAuthStore } from '@/store/auth';

const { Title, Text, Paragraph } = Typography;

interface LoginResponse {
  accessToken: string;
  tokenType: string;
  user: {
    userId: number;
    username: string;
    fullName?: string | null;
    role: string;
    scenarioId: number;
  };
}

export const LoginPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const setAuth = useAuthStore((s) => s.setAuth);

  const from = (location.state as { from?: Location })?.from?.pathname || '/review';

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const { data } = await apiClient.post<LoginResponse>('/api/v1.6/auth/login', values);
      setAuth(data.accessToken, {
        userId: data.user.userId,
        username: data.user.username,
        fullName: data.user.fullName,
        role: data.user.role,
        scenarioId: data.user.scenarioId,
      });
      message.success('登录成功');
      navigate(from, { replace: true });
    } catch (error: any) {
      const msg =
        error?.response?.data?.detail ||
        error?.message ||
        '登录失败，请检查用户名和密码';
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
      }}
    >
      <Card
        style={{
          width: 400,
          borderRadius: 12,
          boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <Title level={2} style={{ marginBottom: 8, fontWeight: 600 }}>
            系统登录
          </Title>
          <Text type="secondary">欢迎使用知识库管理系统</Text>
        </div>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              prefix={<UserOutlined style={{ color: 'rgba(0,0,0,0.25)' }} />}
              placeholder="请输入用户名"
              size="large"
            />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: 'rgba(0,0,0,0.25)' }} />}
              placeholder="请输入密码"
              size="large"
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0, marginTop: 24 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              size="large"
              style={{ height: 44, fontSize: 16, fontWeight: 500 }}
            >
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

