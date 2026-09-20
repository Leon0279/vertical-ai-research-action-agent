import {
  DatabaseOutlined,
  EyeOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import type { ColumnsType } from 'antd/es/table';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Timeline,
  Typography,
} from 'antd';
import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';

import type {
  ActionMemoryItemResponse,
  DecisionMemoryItemResponse,
  MemoryCollectionSummaryResponse,
  PolicyMemoryItemResponse,
  ResearchKnowledgeMemoryItemResponse,
} from '../api/generated/types.gen';
import {
  api,
  type ActionStatus,
  type VisibilityScope,
} from '../api/services';
import { JsonViewer } from '../components/JsonViewer';
import { PageHeading } from '../components/PageHeading';
import { RequestError } from '../components/RequestError';
import { useWorkspace } from '../state/workspace';

const formatDate = (value?: string | null) =>
  value
    ? new Intl.DateTimeFormat('zh-CN', {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(value))
    : '—';

const confidenceText = (value?: number | null) =>
  value == null ? '—' : `${Math.round(value * 100)}%`;

const isDefined = <T,>(value: T | undefined): value is T => value !== undefined;

interface CollectionTableProps<T extends object> {
  columns: ColumnsType<T>;
  data: T[];
  error: unknown;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  loading: boolean;
  rowKey: (record: T) => string;
  onLoadMore: () => void;
}

function CollectionTable<T extends object>({
  columns,
  data,
  error,
  hasNextPage,
  isFetchingNextPage,
  loading,
  rowKey,
  onLoadMore,
}: CollectionTableProps<T>) {
  if (error) {
    return <RequestError error={error} />;
  }
  return (
    <Space direction="vertical" size="middle" className="full-width">
      <Table<T>
        columns={columns}
        dataSource={data}
        rowKey={rowKey}
        loading={loading}
        pagination={false}
        locale={{ emptyText: <Empty description="没有匹配的 Memory" /> }}
        scroll={{ x: 900 }}
        size="middle"
      />
      {hasNextPage ? (
        <Button onClick={onLoadMore} loading={isFetchingNextPage}>
          加载下一页
        </Button>
      ) : data.length ? (
        <Typography.Text type="secondary">已加载全部 {data.length} 条记录</Typography.Text>
      ) : null}
    </Space>
  );
}

function SummaryCard({
  title,
  value,
}: {
  title: string;
  value?: MemoryCollectionSummaryResponse;
}) {
  return (
    <Card size="small" className="summary-card">
      <Statistic title={title} value={value?.count ?? 0} />
      <Typography.Text type="secondary">
        最近更新：{formatDate(value?.last_updated_at)}
      </Typography.Text>
    </Card>
  );
}

export function MemoryPage() {
  const workspace = useWorkspace();
  const [contextForm] = Form.useForm<{ userId: string; projectId: string }>();
  const [activeTab, setActiveTab] = useState('summary');
  const [actionStatuses, setActionStatuses] = useState<ActionStatus[]>([]);
  const [visibilityScopes, setVisibilityScopes] = useState<VisibilityScope[]>([]);
  const [inspected, setInspected] = useState<unknown>(null);
  const enabled = Boolean(workspace.userId && workspace.projectId);

  const summary = useQuery({
    queryKey: ['memory', 'summary', workspace.userId, workspace.projectId],
    queryFn: ({ signal }) =>
      api.memorySummary(workspace.userId, workspace.projectId, signal),
    enabled: enabled && activeTab === 'summary',
  });

  const decisions = useInfiniteQuery({
    queryKey: ['memory', 'decisions', workspace.userId, workspace.projectId],
    queryFn: ({ pageParam, signal }) =>
      api.decisions(workspace.userId, workspace.projectId, pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: enabled && activeTab === 'decisions',
  });

  const actions = useInfiniteQuery({
    queryKey: [
      'memory',
      'actions',
      workspace.userId,
      workspace.projectId,
      actionStatuses,
    ],
    queryFn: ({ pageParam, signal }) =>
      api.actions(
        workspace.userId,
        workspace.projectId,
        actionStatuses,
        pageParam,
        signal,
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: enabled && activeTab === 'actions',
  });

  const policies = useInfiniteQuery({
    queryKey: ['memory', 'policies', workspace.userId, workspace.projectId],
    queryFn: ({ pageParam, signal }) =>
      api.policies(workspace.userId, workspace.projectId, pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: enabled && activeTab === 'policies',
  });

  const research = useInfiniteQuery({
    queryKey: [
      'memory',
      'research',
      workspace.userId,
      workspace.projectId,
      visibilityScopes,
    ],
    queryFn: ({ pageParam, signal }) =>
      api.researchKnowledge(
        workspace.userId,
        workspace.projectId,
        visibilityScopes,
        pageParam,
        signal,
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: enabled && activeTab === 'research',
  });

  const session = useQuery({
    queryKey: ['memory', 'session', workspace.userId, workspace.sessionId],
    queryFn: ({ signal }) =>
      api.sessionMemory(workspace.userId, workspace.sessionId, signal),
    enabled:
      activeTab === 'session' && Boolean(workspace.userId && workspace.sessionId),
    retry: false,
  });

  const decisionItems = useMemo(
    () =>
      decisions.data?.pages
        .flatMap((page) => page.items ?? [])
        .filter(isDefined) ?? [],
    [decisions.data],
  );
  const actionItems = useMemo(
    () =>
      actions.data?.pages
        .flatMap((page) => page.items ?? [])
        .filter(isDefined) ?? [],
    [actions.data],
  );
  const policyItems = useMemo(
    () =>
      policies.data?.pages
        .flatMap((page) => page.items ?? [])
        .filter(isDefined) ?? [],
    [policies.data],
  );
  const researchItems = useMemo(
    () =>
      research.data?.pages
        .flatMap((page) => page.items ?? [])
        .filter(isDefined) ?? [],
    [research.data],
  );

  const inspectColumn = <T extends object>(): ColumnsType<T>[number] => ({
    title: '详情',
    key: 'inspect',
    fixed: 'right',
    width: 88,
    render: (_: unknown, record: T) => (
      <Button size="small" icon={<EyeOutlined />} onClick={() => setInspected(record)}>
        JSON
      </Button>
    ),
  });

  const decisionColumns: ColumnsType<DecisionMemoryItemResponse> = [
    {
      title: '决策',
      dataIndex: 'decision_title',
      width: 220,
      render: (value, record) => value ?? record.decision_question ?? '未命名决策',
    },
    { title: '选择', dataIndex: 'chosen_option', width: 180, render: (value) => value ?? '—' },
    { title: '状态', dataIndex: 'decision_state', width: 110, render: (value) => <Tag>{value ?? '—'}</Tag> },
    { title: '置信度', dataIndex: 'confidence', width: 100, render: confidenceText },
    { title: '更新时间', dataIndex: 'updated_at', width: 180, render: formatDate },
    inspectColumn<DecisionMemoryItemResponse>(),
  ];

  const actionColumns: ColumnsType<ActionMemoryItemResponse> = [
    { title: '行动项', dataIndex: 'action_title', width: 220, render: (value) => value ?? '未命名行动项' },
    { title: '状态', dataIndex: 'action_status', width: 130, render: (value) => <Tag color={value === 'blocked' ? 'error' : value === 'done' ? 'success' : 'blue'}>{value}</Tag> },
    { title: '优先级', dataIndex: 'priority', width: 100, render: (value) => value ?? '—' },
    { title: '负责人', dataIndex: 'owner', width: 120, render: (value) => value ?? '—' },
    { title: '截止时间', dataIndex: 'due_at', width: 180, render: formatDate },
    inspectColumn<ActionMemoryItemResponse>(),
  ];

  const policyColumns: ColumnsType<PolicyMemoryItemResponse> = [
    { title: '策略内容', dataIndex: 'policy_text', width: 320 },
    { title: '类型', dataIndex: 'policy_type', width: 150 },
    { title: 'Owner Scope', dataIndex: 'owner_scope_type', width: 130, render: (value) => <Tag>{value}</Tag> },
    { title: '优先级', dataIndex: 'priority', width: 100, render: (value) => value ?? '—' },
    { title: '置信度', dataIndex: 'confidence', width: 100, render: confidenceText },
    inspectColumn<PolicyMemoryItemResponse>(),
  ];

  const researchColumns: ColumnsType<ResearchKnowledgeMemoryItemResponse> = [
    { title: '知识标题', dataIndex: 'title', width: 260 },
    { title: '类型', dataIndex: 'knowledge_type', width: 140 },
    { title: '可见范围', dataIndex: 'visibility_scope_effective', width: 130, render: (value) => <Tag color="geekblue">{value}</Tag> },
    { title: '新鲜度', dataIndex: 'freshness_status', width: 110, render: (value) => <Tag color={value === 'stale' ? 'error' : value === 'aging' ? 'warning' : 'success'}>{value ?? '—'}</Tag> },
    { title: '置信度', dataIndex: 'confidence', width: 100, render: confidenceText },
    inspectColumn<ResearchKnowledgeMemoryItemResponse>(),
  ];

  const noProject = !enabled ? (
    <Empty
      image={<DatabaseOutlined className="empty-icon" />}
      description="请先设置 User ID 和 Project ID"
    />
  ) : null;

  const tabItems: { key: string; label: string; children: ReactNode }[] = [
    {
      key: 'summary',
      label: '概览',
      children: noProject ?? (
        summary.isError ? (
          <RequestError error={summary.error} />
        ) : (
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} xl={8}><SummaryCard title="Project Profile" value={summary.data?.project_profile} /></Col>
            <Col xs={24} sm={12} xl={8}><SummaryCard title="Decisions" value={summary.data?.decisions} /></Col>
            <Col xs={24} sm={12} xl={8}><SummaryCard title="Actions" value={summary.data?.actions} /></Col>
            <Col xs={24} sm={12} xl={8}><SummaryCard title="Policies" value={summary.data?.policies} /></Col>
            <Col xs={24} sm={12} xl={8}><SummaryCard title="Research Knowledge" value={summary.data?.research_knowledge} /></Col>
          </Row>
        )
      ),
    },
    {
      key: 'decisions',
      label: 'Decisions',
      children: noProject ?? (
        <CollectionTable<DecisionMemoryItemResponse>
          columns={decisionColumns}
          data={decisionItems}
          error={decisions.error}
          loading={decisions.isPending}
          hasNextPage={Boolean(decisions.hasNextPage)}
          isFetchingNextPage={decisions.isFetchingNextPage}
          onLoadMore={() => void decisions.fetchNextPage()}
          rowKey={(record) => record.decision_id}
        />
      ),
    },
    {
      key: 'actions',
      label: 'Actions',
      children: noProject ?? (
        <Space direction="vertical" size="middle" className="full-width">
          <Select<ActionStatus[]>
            mode="multiple"
            allowClear
            placeholder="按状态筛选；留空使用后端默认值"
            value={actionStatuses}
            onChange={setActionStatuses}
            className="filter-select"
            options={[
              { value: 'todo', label: 'todo' },
              { value: 'in_progress', label: 'in_progress' },
              { value: 'blocked', label: 'blocked' },
              { value: 'done', label: 'done' },
              { value: 'cancelled', label: 'cancelled' },
            ]}
          />
          <CollectionTable<ActionMemoryItemResponse>
            columns={actionColumns}
            data={actionItems}
            error={actions.error}
            loading={actions.isPending}
            hasNextPage={Boolean(actions.hasNextPage)}
            isFetchingNextPage={actions.isFetchingNextPage}
            onLoadMore={() => void actions.fetchNextPage()}
            rowKey={(record) => record.action_id}
          />
        </Space>
      ),
    },
    {
      key: 'policies',
      label: 'Policies',
      children: noProject ?? (
        <CollectionTable<PolicyMemoryItemResponse>
          columns={policyColumns}
          data={policyItems}
          error={policies.error}
          loading={policies.isPending}
          hasNextPage={Boolean(policies.hasNextPage)}
          isFetchingNextPage={policies.isFetchingNextPage}
          onLoadMore={() => void policies.fetchNextPage()}
          rowKey={(record) => record.policy_id}
        />
      ),
    },
    {
      key: 'research',
      label: 'Research Knowledge',
      children: noProject ?? (
        <Space direction="vertical" size="middle" className="full-width">
          <Select<VisibilityScope[]>
            mode="multiple"
            allowClear
            placeholder="按可见范围筛选；留空仅查询项目级知识"
            value={visibilityScopes}
            onChange={setVisibilityScopes}
            className="filter-select"
            options={[
              { value: 'project', label: 'project' },
              { value: 'user', label: 'user' },
              { value: 'domain', label: 'domain' },
              { value: 'global', label: 'global' },
            ]}
          />
          <CollectionTable<ResearchKnowledgeMemoryItemResponse>
            columns={researchColumns}
            data={researchItems}
            error={research.error}
            loading={research.isPending}
            hasNextPage={Boolean(research.hasNextPage)}
            isFetchingNextPage={research.isFetchingNextPage}
            onLoadMore={() => void research.fetchNextPage()}
            rowKey={(record) => record.knowledge_id}
          />
        </Space>
      ),
    },
    {
      key: 'session',
      label: 'Session Memory',
      children: session.isError ? (
        <RequestError error={session.error} />
      ) : session.data ? (
        <Space direction="vertical" size="large" className="full-width">
          <Descriptions bordered column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="Session ID" span={2}>
              <Typography.Text copyable code>{session.data.session_id}</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="更新时间">{formatDate(session.data.updated_at)}</Descriptions.Item>
            <Descriptions.Item label="过期时间">{formatDate(session.data.expires_at)}</Descriptions.Item>
            <Descriptions.Item label="工作摘要" span={2}>{session.data.session_working_summary ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="最新建议" span={2}>{session.data.latest_recommendation ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="当前任务" span={2}>{session.data.current_local_task_framing ?? '—'}</Descriptions.Item>
          </Descriptions>
          <Card size="small" title="近期对话摘要">
            <Timeline items={(session.data.recent_turn_summaries ?? []).map((turn) => ({ children: <><Tag>{turn.role}</Tag>{turn.content_summary}<div><Typography.Text type="secondary">{formatDate(turn.created_at)}</Typography.Text></div></> }))} />
          </Card>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <Card size="small" title="最新行动项">
                {(session.data.latest_action_items ?? []).length ? (
                  <ul className="compact-list">
                    {(session.data.latest_action_items ?? []).map((item) => <li key={item}>{item}</li>)}
                  </ul>
                ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无" />}
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card size="small" title="开放问题">
                {(session.data.open_questions ?? []).length ? (
                  <ul className="compact-list">
                    {(session.data.open_questions ?? []).map((item) => <li key={item}>{item}</li>)}
                  </ul>
                ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无" />}
              </Card>
            </Col>
          </Row>
          <JsonViewer value={session.data} />
        </Space>
      ) : session.isPending ? (
        <Card loading />
      ) : (
        <Empty description="请输入有效的 User ID 和 Session ID" />
      ),
    },
  ];

  return (
    <div>
      <PageHeading
        title="Memory 检查器"
        description="浏览当前项目的长期记忆及指定 Session 的短期工作记忆。"
      />
      <Card className="context-card" title="查询上下文">
        <Form
          form={contextForm}
          layout="inline"
          initialValues={{ userId: workspace.userId, projectId: workspace.projectId }}
          onFinish={(values) => workspace.updateWorkspace(values)}
        >
          <Form.Item name="userId" label="User ID" rules={[{ required: true, whitespace: true }]}>
            <Input placeholder="local-demo" />
          </Form.Item>
          <Form.Item name="projectId" label="Project ID" rules={[{ required: true, whitespace: true }]}>
            <Input placeholder="选择或输入项目 ID" />
          </Form.Item>
          <Form.Item>
            <Button htmlType="submit" type="primary" icon={<ReloadOutlined />}>应用并刷新</Button>
          </Form.Item>
        </Form>
        <Typography.Text type="secondary">
          Session Memory 使用当前 Session ID：<Typography.Text code copyable>{workspace.sessionId}</Typography.Text>
        </Typography.Text>
      </Card>

      <Card className="section-gap memory-tabs-card">
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} destroyOnHidden={false} />
      </Card>

      <Drawer
        title="Memory 原始记录"
        size={Math.min(720, window.innerWidth)}
        open={inspected !== null}
        onClose={() => setInspected(null)}
      >
        <JsonViewer value={inspected} />
      </Drawer>
    </div>
  );
}
