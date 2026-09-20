import {
  BookOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  LinkOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Card,
  Col,
  Descriptions,
  Empty,
  Progress,
  Row,
  Space,
  Tabs,
  Tag,
  Timeline,
  Typography,
} from 'antd';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import type { AgentRunResponse } from '../api/generated/types.gen';
import { JsonViewer } from './JsonViewer';

const isWebUrl = (source: string) => {
  try {
    const url = new URL(source);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
};

export function AgentResult({ result }: { result: AgentRunResponse }) {
  const confidence =
    result.confidence == null
      ? undefined
      : Math.max(0, Math.min(100, Math.round(result.confidence * 100)));

  const answer = (
    <div className="markdown-output">
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>
        {result.answer}
      </ReactMarkdown>
    </div>
  );

  const actions = (result.action_items ?? []).length ? (
    <div className="record-list">
      {(result.action_items ?? []).map((item) => (
        <div className="record-list-item" key={`${item.title}-${item.priority}`}>
          <CheckCircleOutlined className="list-icon" />
          <div>
            <div className="record-list-title">
              <Space wrap>
                <Typography.Text strong>{item.title}</Typography.Text>
                <Tag>{item.priority}</Tag>
              </Space>
            </div>
            <Typography.Text type="secondary">
              {item.description ?? '无补充说明'}
            </Typography.Text>
          </div>
        </div>
      ))}
    </div>
  ) : (
    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="本次运行没有生成行动项" />
  );

  const citations = (result.citations ?? []).length ? (
    <div className="record-list">
      {(result.citations ?? []).map((citation, index) => (
        <div className="record-list-item" key={`${citation.source}-${index}`}>
          <BookOutlined className="list-icon" />
          <div>
            <div className="record-list-title">
              {isWebUrl(citation.source) ? (
                <Typography.Link
                  href={citation.source}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  [{index + 1}] {citation.source} <LinkOutlined />
                </Typography.Link>
              ) : (
                <Typography.Text>
                  [{index + 1}] {citation.source}
                </Typography.Text>
              )}
            </div>
            <Typography.Text type="secondary">
              {citation.note ?? '无补充说明'}
            </Typography.Text>
          </div>
        </div>
      ))}
    </div>
  ) : (
    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="本次运行没有返回引用" />
  );

  const runtime = (
    <Row gutter={[24, 24]}>
      <Col xs={24} lg={12}>
        <Typography.Title level={5}>执行阶段</Typography.Title>
        <Timeline
          items={(result.stage_history ?? []).map((stage) => ({
            dot: <ClockCircleOutlined />,
            children: <Typography.Text code>{stage}</Typography.Text>,
          }))}
        />
      </Col>
      <Col xs={24} lg={12}>
        <Typography.Title level={5}>运行信息</Typography.Title>
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="Trace ID">
            <Typography.Text copyable={Boolean(result.trace_id)} code>
              {result.trace_id ?? '—'}
            </Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="Task Type">
            {result.task_type}
          </Descriptions.Item>
          <Descriptions.Item label="Workflow">
            {result.workflow_pattern}
          </Descriptions.Item>
        </Descriptions>
        <Typography.Title level={5} className="runtime-metadata-title">
          Metadata
        </Typography.Title>
        <JsonViewer value={result.metadata ?? {}} />
      </Col>
    </Row>
  );

  return (
    <Space direction="vertical" size="large" className="full-width">
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={confidence === undefined ? 24 : 19}>
          <Alert
            type="success"
            showIcon
            title="运行完成"
            description={result.summary}
          />
        </Col>
        {confidence !== undefined ? (
          <Col xs={24} xl={5}>
            <Card size="small" className="confidence-card">
              <Progress type="dashboard" percent={confidence} size={82} />
              <Typography.Text type="secondary">整体置信度</Typography.Text>
            </Card>
          </Col>
        ) : null}
      </Row>

      {result.recommendation ? (
        <Card className="recommendation-card" title="核心建议">
          <Typography.Paragraph>{result.recommendation}</Typography.Paragraph>
        </Card>
      ) : null}

      {(result.caveats ?? []).length ? (
        <Alert
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          title="限制与注意事项"
          description={
            <ul className="compact-list">
              {(result.caveats ?? []).map((caveat) => (
                <li key={caveat}>{caveat}</li>
              ))}
            </ul>
          }
        />
      ) : null}

      <Card>
        <Tabs
          items={[
            { key: 'answer', label: '完整回答', children: answer },
            {
              key: 'actions',
              label: `行动项 (${result.action_items?.length ?? 0})`,
              children: actions,
            },
            {
              key: 'citations',
              label: `引用 (${result.citations?.length ?? 0})`,
              children: citations,
            },
            { key: 'runtime', label: '运行轨迹', children: runtime },
            {
              key: 'raw',
              label: '原始 JSON',
              children: <JsonViewer value={result} />,
            },
          ]}
        />
      </Card>
    </Space>
  );
}
