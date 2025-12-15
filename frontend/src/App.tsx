import React from 'react';
import { Layout, Menu, Typography, Button } from 'antd';
import {
  CheckCircleOutlined,
  DatabaseOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/auth';
import { LoginPage } from '@/pages/LoginPage';
import { ReviewWorkbenchPage } from '@/pages/ReviewWorkbenchPage';
import { KnowledgeManagementPage } from '@/pages/KnowledgeManagementPage';
import { InternalTasksPage } from '@/pages/InternalTasksPage';

const { Header, Content, Sider } = Layout;
const { Text } = Typography;

const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, clearAuth } = useAuthStore();
  const appTitle =
    user?.scenarioId === 2 ? '公交智能知识库系统' : '水务智能知识库系统';

  const onLogout = () => {
    clearAuth();
    navigate('/login');
  };

  const isLogin = location.pathname === '/login';

  const menuItems = [
    {
      key: '/review',
      icon: <CheckCircleOutlined />,
      label: '审核工作台',
    },
    {
      key: '/knowledge',
      icon: <DatabaseOutlined />,
      label: '知识库管理',
    },
  ];

  const selectedKey = location.pathname;

  if (isLogin) {
    return <>{children}</>;
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={200}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          background: '#fff',
          borderRight: '1px solid #f0f0f0',
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 16,
            fontWeight: 'bold',
            borderBottom: '1px solid #f0f0f0',
            color: '#1890ff',
          }}
        >
          {appTitle}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ marginTop: 8, borderRight: 'none' }}
        />
      </Sider>
      <Layout style={{ marginLeft: 200 }}>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center',
            borderBottom: '1px solid #f0f0f0',
            height: 56,
            lineHeight: '56px',
          }}
        >
          <Text type="secondary" style={{ marginRight: 16 }}>
            用户: {user?.fullName || user?.username || '未登录'}
          </Text>
          <Button icon={<LogoutOutlined />} onClick={onLogout}>
            退出
          </Button>
        </Header>
        <Content style={{ margin: 16, minHeight: 'calc(100vh - 88px)' }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

const RequireAuth: React.FC<{ children: React.ReactElement }> = ({ children }) => {
  const { accessToken } = useAuthStore();
  const location = useLocation();

  if (!accessToken) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
};

const App: React.FC = () => (
  <AppShell>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/review"
        element={
          <RequireAuth>
            <ReviewWorkbenchPage />
          </RequireAuth>
        }
      />
      <Route
        path="/knowledge"
        element={
          <RequireAuth>
            <KnowledgeManagementPage />
          </RequireAuth>
        }
      />
      <Route
        path="/internal-tasks/trigger-panel-ab12cd34"
        element={
          <RequireAuth>
            <InternalTasksPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/review" replace />} />
    </Routes>
  </AppShell>
);

export default App;
