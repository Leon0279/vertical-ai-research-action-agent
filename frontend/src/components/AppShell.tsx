import {
  AppstoreOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  GithubOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { Button, Layout, Menu, Space, Tag, Typography } from 'antd';
import { useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';

import { useWorkspace } from '../state/workspace';
import { HealthStatus } from './HealthStatus';

const { Header, Sider, Content } = Layout;

const navigation = [
  { key: '/agent', icon: <ExperimentOutlined />, label: 'Agent Playground' },
  { key: '/projects', icon: <AppstoreOutlined />, label: '项目管理' },
  { key: '/memory', icon: <DatabaseOutlined />, label: 'Memory 检查器' },
];

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { userId, projectId } = useWorkspace();

  return (
    <Layout className="app-layout">
      <Sider
        breakpoint="lg"
        collapsedWidth={72}
        collapsed={collapsed}
        onCollapse={setCollapsed}
        className="app-sider"
        width={248}
      >
        <div className="brand">
          <div className="brand-mark">V</div>
          {!collapsed ? (
            <div>
              <div className="brand-title">Vertical AI</div>
              <div className="brand-subtitle">Research Agent</div>
            </div>
          ) : null}
        </div>
        <Menu
          mode="inline"
          theme="dark"
          selectedKeys={[location.pathname]}
          items={navigation}
          onClick={({ key }) => navigate(key)}
          className="app-menu"
        />
        {!collapsed ? (
          <div className="sider-footnote">
            <GithubOutlined /> 本地开发调试台
          </div>
        ) : null}
      </Sider>
      <Layout>
        <Header className="app-header">
          <Button
            type="text"
            aria-label={collapsed ? '展开导航' : '收起导航'}
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed((value) => !value)}
          />
          <Space className="header-context" size="small" wrap>
            <Tag variant="filled">用户：{userId || '未设置'}</Tag>
            <Tag variant="filled" color={projectId ? 'blue' : 'default'}>
              项目：{projectId || '未选择'}
            </Tag>
          </Space>
          <HealthStatus />
        </Header>
        <Content className="app-content">
          <Outlet />
          <footer className="app-footer">
            <Typography.Text type="secondary">
              Vertical AI Research &amp; Action Agent · Local Debug Console
            </Typography.Text>
          </footer>
        </Content>
      </Layout>
    </Layout>
  );
}
