import {
  ApiOutlined,
  CloseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useMutation } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Space,
  Spin,
  Typography,
} from 'antd';
import { useEffect, useRef } from 'react';

import type {
  AgentRunRequest,
  AgentRunResponse,
} from '../api/generated/types.gen';
import { api } from '../api/services';
import { AgentResult } from '../components/AgentResult';
import { PageHeading } from '../components/PageHeading';
import { RequestError } from '../components/RequestError';
import { useElapsedSeconds } from '../hooks/useElapsedSeconds';
import { useWorkspace } from '../state/workspace';

interface AgentFormValues {
  query: string;
  user_id: string;
  session_id: string;
  project_id?: string;
  iteration_budget: number;
}

export function AgentPlaygroundPage() {
  const [form] = Form.useForm<AgentFormValues>();
  const abortController = useRef<AbortController | null>(null);
  const workspace = useWorkspace();

  const mutation = useMutation<
    AgentRunResponse,
    Error,
    { payload: AgentRunRequest; signal: AbortSignal }
  >({
    mutationFn: ({ payload, signal }) => api.runAgent(payload, signal),
  });
  const elapsed = useElapsedSeconds(mutation.isPending);

  useEffect(() => {
    form.setFieldValue('session_id', workspace.sessionId);
  }, [form, workspace.sessionId]);

  const submit = (values: AgentFormValues) => {
    const payload: AgentRunRequest = {
      query: values.query.trim(),
      user_id: values.user_id.trim(),
      session_id: values.session_id.trim(),
      project_id: values.project_id?.trim() || null,
      iteration_budget: values.iteration_budget,
    };
    workspace.updateWorkspace({
      userId: payload.user_id,
      projectId: payload.project_id ?? '',
      sessionId: payload.session_id ?? workspace.sessionId,
      iterationBudget: payload.iteration_budget ?? 2,
    });

    const controller = new AbortController();
    abortController.current = controller;
    mutation.mutate(
      { payload, signal: controller.signal },
      {
        onSettled: () => {
          if (abortController.current === controller) {
            abortController.current = null;
          }
        },
      },
    );
  };

  const cancel = () => {
    abortController.current?.abort();
    mutation.reset();
  };

  const createSession = () => {
    workspace.newSession();
    mutation.reset();
  };

  return (
    <div>
      <PageHeading
        title="Agent Playground"
        description="构造一次完整运行请求，并检查结构化结论、证据引用与执行轨迹。"
        extra={
          <Button icon={<PlusOutlined />} onClick={createSession}>
            新建 Session
          </Button>
        }
      />

      <Card className="request-card" title="运行参数">
        <Form<AgentFormValues>
          form={form}
          layout="vertical"
          initialValues={{
            query: '',
            user_id: workspace.userId,
            session_id: workspace.sessionId,
            project_id: workspace.projectId,
            iteration_budget: workspace.iterationBudget,
          }}
          onFinish={submit}
          requiredMark="optional"
        >
          <Form.Item
            name="query"
            label="研究请求"
            rules={[
              { required: true, whitespace: true, message: '请输入研究请求' },
            ]}
          >
            <Input.TextArea
              rows={6}
              maxLength={12_000}
              showCount
              placeholder="例如：比较 RAG 与长上下文方案在企业知识库中的适用场景，并给出实施建议。"
            />
          </Form.Item>

          <Row gutter={16}>
            <Col xs={24} md={12} xl={6}>
              <Form.Item
                name="user_id"
                label="User ID"
                rules={[{ required: true, whitespace: true, message: '请输入 User ID' }]}
              >
                <Input placeholder="local-demo" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12} xl={7}>
              <Form.Item
                name="project_id"
                label="Project ID"
                tooltip="可选；用于加载和写回项目范围 Memory"
              >
                <Input allowClear placeholder="未选择项目" />
              </Form.Item>
            </Col>
            <Col xs={24} md={16} xl={8}>
              <Form.Item
                name="session_id"
                label="Session ID"
                rules={[{ required: true, whitespace: true, message: '请输入 Session ID' }]}
              >
                <Input />
              </Form.Item>
            </Col>
            <Col xs={24} md={8} xl={3}>
              <Form.Item
                name="iteration_budget"
                label="迭代预算"
                rules={[{ required: true, message: '请选择迭代预算' }]}
              >
                <InputNumber min={1} max={5} className="full-width" />
              </Form.Item>
            </Col>
          </Row>

          <Space>
            <Button
              htmlType="submit"
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={mutation.isPending}
              size="large"
            >
              运行 Agent
            </Button>
            {mutation.isPending ? (
              <Button
                danger
                icon={<CloseCircleOutlined />}
                onClick={cancel}
                size="large"
              >
                取消等待
              </Button>
            ) : null}
          </Space>
        </Form>
      </Card>

      {mutation.isPending ? (
        <Card className="result-loading">
          <Spin size="large" />
          <div>
            <Typography.Title level={4}>Agent 正在执行</Typography.Title>
            <Typography.Text type="secondary">
              已等待 {elapsed} 秒。当前接口为非流式调用，完成后将一次性显示结果。
            </Typography.Text>
          </div>
        </Card>
      ) : null}

      {mutation.isError ? (
        <div className="section-gap">
          <RequestError error={mutation.error} />
        </div>
      ) : null}

      {!mutation.data && !mutation.isPending && !mutation.isError ? (
        <Alert
          className="section-gap"
          type="info"
          showIcon
          icon={<ApiOutlined />}
          title="尚未运行"
          description="填写参数后调用现有 POST /v1/agent/run。真实运行可能使用外部 Provider 额度。"
        />
      ) : null}

      {mutation.data ? (
        <div className="section-gap">
          <AgentResult result={mutation.data} />
        </div>
      ) : null}
    </div>
  );
}
