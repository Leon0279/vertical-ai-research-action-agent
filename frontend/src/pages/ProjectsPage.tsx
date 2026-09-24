import {
  FolderOpenOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Row,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import { useState } from 'react';

import type { CreateProjectRequest } from '../api/generated/types.gen';
import { api } from '../api/services';
import { PageHeading } from '../components/PageHeading';
import { RequestError } from '../components/RequestError';
import { useWorkspace } from '../state/workspace';

const formatDate = (value?: string | null) =>
  value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—';

export function ProjectsPage() {
  const workspace = useWorkspace();
  const [lookupUser, setLookupUser] = useState({
    owner: workspace.userId,
    value: workspace.userId,
  });
  const lookupUserId =
    lookupUser.owner === workspace.userId
      ? lookupUser.value
      : workspace.userId;
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm<CreateProjectRequest>();
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();

  const projects = useQuery({
    queryKey: ['projects', workspace.userId],
    queryFn: ({ signal }) => api.listProjects(workspace.userId, signal),
    enabled: Boolean(workspace.userId),
  });
  const projectIds = (projects.data?.project_ids ?? []).filter(
    (projectId): projectId is string => typeof projectId === 'string',
  );
  const details = useQuery({
    queryKey: ['project', workspace.userId, workspace.projectId],
    queryFn: ({ signal }) =>
      api.getProject(workspace.userId, workspace.projectId, signal),
    enabled: Boolean(workspace.userId && workspace.projectId),
  });

  const createProject = useMutation({
    mutationFn: (payload: CreateProjectRequest) => api.createProject(payload),
    onSuccess: async (result) => {
      workspace.updateWorkspace({ projectId: result.project_id });
      setCreateOpen(false);
      form.resetFields();
      await queryClient.invalidateQueries({
        queryKey: ['projects', workspace.userId],
      });
      void messageApi.success(`项目已创建：${result.project_id}`);
    },
  });

  const search = () => {
    const nextUserId = lookupUserId.trim();
    if (nextUserId) {
      workspace.updateWorkspace({ userId: nextUserId, projectId: '' });
    }
  };

  const openCreate = () => {
    form.setFieldsValue({ user_id: workspace.userId, constraints: [] });
    createProject.reset();
    setCreateOpen(true);
  };

  return (
    <div>
      {contextHolder}
      <PageHeading
        title="项目管理"
        description="创建和选择项目上下文；当前项目会同步到 Agent Playground 与 Memory 检查器。"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            创建项目
          </Button>
        }
      />

      <Card className="context-card">
        <Space.Compact className="project-search">
          <Input
            aria-label="查询用户 ID"
            value={lookupUserId}
            onChange={(event) =>
              setLookupUser({
                owner: workspace.userId,
                value: event.target.value,
              })
            }
            onPressEnter={search}
            prefix={<SearchOutlined />}
            placeholder="输入 User ID"
          />
          <Button type="primary" onClick={search}>
            查询
          </Button>
          <Button
            aria-label="刷新项目"
            icon={<ReloadOutlined />}
            onClick={() => void projects.refetch()}
          />
        </Space.Compact>
      </Card>

      {projects.isError ? (
        <div className="section-gap">
          <RequestError error={projects.error} />
        </div>
      ) : null}

      <Row gutter={[20, 20]} className="section-gap">
        <Col xs={24} lg={8}>
          <Card title={`项目列表 (${projects.data?.project_ids?.length ?? 0})`} loading={projects.isPending}>
            {projectIds.length ? (
              <div className="record-list">
                {projectIds.map((projectId) => (
                <button
                  type="button"
                  key={projectId}
                  className={
                    projectId === workspace.projectId
                      ? 'project-list-item project-list-item-active'
                      : 'project-list-item'
                  }
                  onClick={() => workspace.updateWorkspace({ projectId })}
                >
                  <FolderOpenOutlined className="list-icon" />
                  <Typography.Text code>{projectId}</Typography.Text>
                  {projectId === workspace.projectId ? (
                    <Tag color="blue">当前</Tag>
                  ) : (
                    <Typography.Text type="secondary">选择</Typography.Text>
                  )}
                </button>
                ))}
              </div>
            ) : (
              <Empty description="当前用户还没有项目" />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card title="项目详情" loading={details.isPending && Boolean(workspace.projectId)}>
            {!workspace.projectId ? (
              <Empty description="请先选择一个项目" />
            ) : details.isError ? (
              <RequestError error={details.error} />
            ) : details.data ? (
              <Descriptions bordered column={{ xs: 1, md: 2 }}>
                <Descriptions.Item label="Project ID" span={2}>
                  <Typography.Text copyable code>{details.data.project_id}</Typography.Text>
                </Descriptions.Item>
                <Descriptions.Item label="名称">{details.data.project_name ?? '—'}</Descriptions.Item>
                <Descriptions.Item label="领域">{details.data.domain ?? '—'}</Descriptions.Item>
                <Descriptions.Item label="当前阶段">{details.data.current_stage ?? '—'}</Descriptions.Item>
                <Descriptions.Item label="更新时间">{formatDate(details.data.profile_updated_at)}</Descriptions.Item>
                <Descriptions.Item label="描述" span={2}>{details.data.project_description ?? '—'}</Descriptions.Item>
                <Descriptions.Item label="目标" span={2}>{details.data.project_goal ?? '—'}</Descriptions.Item>
                <Descriptions.Item label="约束" span={2}>
                  <Space wrap>
                    {(details.data.constraints ?? []).length
                      ? details.data.constraints?.map((constraint) => <Tag key={constraint}>{constraint}</Tag>)
                      : '—'}
                  </Space>
                </Descriptions.Item>
                <Descriptions.Item label="重要上下文" span={2}>{details.data.important_context ?? '—'}</Descriptions.Item>
              </Descriptions>
            ) : (
              <Empty description="暂无详情" />
            )}
          </Card>
        </Col>
      </Row>

      <Modal
        title="创建项目"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => form.submit()}
        okText="创建"
        cancelText="取消"
        confirmLoading={createProject.isPending}
        width={720}
      >
        <Form<CreateProjectRequest>
          form={form}
          layout="vertical"
          onFinish={(values) => createProject.mutate(values)}
          requiredMark="optional"
        >
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item name="user_id" label="User ID" rules={[{ required: true, whitespace: true }]}>
                <Input maxLength={200} />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item name="project_name" label="项目名称" rules={[{ required: true, whitespace: true }]}>
                <Input maxLength={200} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="project_description" label="项目描述" rules={[{ required: true, whitespace: true }]}>
            <Input.TextArea rows={3} maxLength={5000} showCount />
          </Form.Item>
          <Form.Item name="project_goal" label="项目目标">
            <Input.TextArea rows={2} maxLength={2000} showCount />
          </Form.Item>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item name="domain" label="领域">
                <Input maxLength={200} />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item name="current_stage" label="当前阶段">
                <Input maxLength={200} />
              </Form.Item>
            </Col>
          </Row>
          <Form.List name="constraints">
            {(fields, { add, remove }) => (
              <Form.Item label="长期约束">
                <Space direction="vertical" className="full-width">
                  {fields.map((field) => (
                    <Space.Compact key={field.key} className="full-width">
                      <Form.Item {...field} noStyle rules={[{ required: true, whitespace: true }]}>
                        <Input maxLength={500} placeholder="输入一条约束" />
                      </Form.Item>
                      <Button danger onClick={() => remove(field.name)}>删除</Button>
                    </Space.Compact>
                  ))}
                  {fields.length < 20 ? <Button onClick={() => add()} icon={<PlusOutlined />}>添加约束</Button> : null}
                </Space>
              </Form.Item>
            )}
          </Form.List>
          <Form.Item name="important_context" label="重要上下文">
            <Input.TextArea rows={3} maxLength={5000} showCount />
          </Form.Item>
          {createProject.isError ? <RequestError error={createProject.error} /> : null}
        </Form>
      </Modal>
    </div>
  );
}
