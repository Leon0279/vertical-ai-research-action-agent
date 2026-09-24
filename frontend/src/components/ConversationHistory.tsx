import {
  BookOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useInfiniteQuery } from '@tanstack/react-query';
import {
  Button,
  Card,
  Collapse,
  Empty,
  Progress,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd';
import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import type {
  ConversationAssistantDetailsResponse,
  ConversationMessageResponse,
} from '../api/generated/types.gen';
import { api } from '../api/services';
import { RequestError } from './RequestError';

const rolePresentation = {
  user: { label: '用户', color: 'blue' },
  assistant: { label: 'Agent', color: 'green' },
  system: { label: '系统', color: 'purple' },
  tool: { label: '工具', color: 'orange' },
} as const;

const formatDate = (value: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
  }).format(new Date(value));

const isWebUrl = (source: string) => {
  try {
    const url = new URL(source);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
};

function MessageContent({ message }: { message: ConversationMessageResponse }) {
  if (message.content_format === 'markdown') {
    return (
      <div className="markdown-output conversation-markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>
          {message.content}
        </ReactMarkdown>
      </div>
    );
  }

  if (message.content_format === 'json') {
    let content = message.content;
    try {
      content = JSON.stringify(JSON.parse(message.content), null, 2);
    } catch {
      // Keep historical invalid JSON readable instead of hiding the message.
    }
    return <pre className="conversation-json">{content}</pre>;
  }

  return <div className="conversation-text">{message.content}</div>;
}

function AssistantDetails({ details }: { details: ConversationAssistantDetailsResponse }) {
  const confidence =
    details.confidence == null
      ? undefined
      : Math.max(0, Math.min(100, Math.round(details.confidence * 100)));

  return (
    <Collapse
      ghost
      size="small"
      className="conversation-details"
      items={[
        {
          key: 'details',
          label: '查看结构化详情',
          children: (
            <Space direction="vertical" size="middle" className="full-width">
              {details.summary ? (
                <div>
                  <Typography.Text strong>摘要</Typography.Text>
                  <Typography.Paragraph>{details.summary}</Typography.Paragraph>
                </div>
              ) : null}
              {details.recommendation ? (
                <div>
                  <Typography.Text strong>建议</Typography.Text>
                  <Typography.Paragraph>{details.recommendation}</Typography.Paragraph>
                </div>
              ) : null}
              {confidence !== undefined ? (
                <div className="conversation-confidence">
                  <Typography.Text strong>置信度</Typography.Text>
                  <Progress percent={confidence} size="small" />
                </div>
              ) : null}
              {(details.action_items ?? []).length ? (
                <div>
                  <Typography.Text strong>行动项</Typography.Text>
                  <div className="record-list">
                    {(details.action_items ?? []).map((item, index) => (
                      <div className="record-list-item" key={`${item.title}-${index}`}>
                        <CheckCircleOutlined className="list-icon" />
                        <div>
                          <Space wrap>
                            <Typography.Text>{item.title}</Typography.Text>
                            <Tag>{item.priority}</Tag>
                          </Space>
                          {item.description ? (
                            <div><Typography.Text type="secondary">{item.description}</Typography.Text></div>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {(details.citations ?? []).length ? (
                <div>
                  <Typography.Text strong>引用</Typography.Text>
                  <div className="record-list">
                    {(details.citations ?? []).map((citation, index) => (
                      <div className="record-list-item" key={`${citation.source}-${index}`}>
                        <BookOutlined className="list-icon" />
                        <div>
                          {isWebUrl(citation.source) ? (
                            <Typography.Link href={citation.source} target="_blank" rel="noreferrer noopener">
                              {citation.source}
                            </Typography.Link>
                          ) : (
                            <Typography.Text>{citation.source}</Typography.Text>
                          )}
                          {citation.note ? (
                            <div><Typography.Text type="secondary">{citation.note}</Typography.Text></div>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {(details.caveats ?? []).length ? (
                <div>
                  <Typography.Text strong>限制与注意事项</Typography.Text>
                  <ul className="compact-list">
                    {(details.caveats ?? []).map((caveat) => <li key={caveat}>{caveat}</li>)}
                  </ul>
                </div>
              ) : null}
            </Space>
          ),
        },
      ]}
    />
  );
}

export function ConversationHistory({
  userId,
  sessionId,
}: {
  userId: string;
  sessionId: string;
}) {
  const history = useInfiniteQuery({
    queryKey: ['conversation-messages', userId, sessionId],
    queryFn: ({ pageParam, signal }) =>
      api.listConversationMessages(userId, sessionId, pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: Boolean(userId && sessionId),
  });

  const messages = useMemo(() => {
    const seen = new Set<string>();
    const chronologicalPages = [...(history.data?.pages ?? [])].reverse();
    return chronologicalPages.flatMap((page) =>
      (page.messages ?? []).filter((message) => {
        if (seen.has(message.message_id)) {
          return false;
        }
        seen.add(message.message_id);
        return true;
      }),
    );
  }, [history.data?.pages]);

  return (
    <Card
      className="conversation-history-card"
      title="历史对话"
      extra={<Typography.Text copyable code>{sessionId}</Typography.Text>}
    >
      {history.isPending ? (
        <div className="conversation-loading"><Spin /><span>正在加载历史消息…</span></div>
      ) : history.isError ? (
        <div>
          <RequestError error={history.error} />
          <Button
            className="section-gap"
            icon={<ReloadOutlined />}
            onClick={() => void history.refetch()}
          >
            重新加载
          </Button>
        </div>
      ) : (
        <>
          {history.hasNextPage ? (
            <div className="conversation-load-older">
              <Button
                icon={<ClockCircleOutlined />}
                loading={history.isFetchingNextPage}
                onClick={() => void history.fetchNextPage()}
              >
                加载更早消息
              </Button>
            </div>
          ) : null}
          {messages.length ? (
            <div className="conversation-thread">
              {messages.map((message) => {
                const role = rolePresentation[message.role];
                return (
                  <article
                    className={`conversation-message conversation-message-${message.role}`}
                    key={message.message_id}
                  >
                    <header className="conversation-message-header">
                      <Tag color={role.color}>{role.label}</Tag>
                      <Typography.Text type="secondary">
                        {formatDate(message.created_at)}
                      </Typography.Text>
                    </header>
                    <MessageContent message={message} />
                    {message.role === 'assistant' && message.assistant_details ? (
                      <AssistantDetails details={message.assistant_details} />
                    ) : null}
                  </article>
                );
              })}
            </div>
          ) : (
            <Empty description="这个 Session 还没有历史消息" />
          )}
        </>
      )}
    </Card>
  );
}
