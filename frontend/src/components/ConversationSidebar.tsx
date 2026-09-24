import {
  MessageOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useInfiniteQuery, useQueries } from '@tanstack/react-query';
import { Button, Empty, Input, Skeleton, Space, Tag, Typography } from 'antd';
import { useMemo, useState } from 'react';
import { matchPath, useLocation, useNavigate } from 'react-router-dom';

import type { ConversationSessionSummaryResponse } from '../api/generated/types.gen';
import { readableError } from '../api/errors';
import { api } from '../api/services';
import { useWorkspace } from '../state/workspace';

const formatDate = (value: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));

export function ConversationSidebar({ collapsed }: { collapsed: boolean }) {
  const workspace = useWorkspace();
  const navigate = useNavigate();
  const location = useLocation();
  const [userDraft, setUserDraft] = useState(workspace.userId);
  const [userError, setUserError] = useState('');

  const conversations = useInfiniteQuery({
    queryKey: ['conversations', workspace.userId],
    queryFn: ({ pageParam, signal }) =>
      api.listConversations(workspace.userId, pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: !collapsed && Boolean(workspace.userId),
  });

  const sessions = useMemo(() => {
    const seen = new Set<string>();
    return (conversations.data?.pages ?? []).flatMap((page) =>
      (page.sessions ?? []).filter((session) => {
        if (seen.has(session.session_id)) {
          return false;
        }
        seen.add(session.session_id);
        return true;
      }),
    );
  }, [conversations.data?.pages]);

  const projectIds = useMemo(
    () => [
      ...new Set(
        sessions
          .map((session) => session.project_id)
          .filter((projectId): projectId is string => Boolean(projectId)),
      ),
    ],
    [sessions],
  );
  const projectQueries = useQueries({
    queries: projectIds.map((projectId) => ({
      queryKey: ['project', workspace.userId, projectId],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        api.getProject(workspace.userId, projectId, signal),
      enabled: !collapsed,
    })),
  });
  const projectNames = new Map(
    projectIds.map((projectId, index) => [
      projectId,
      projectQueries[index]?.data?.project_name || undefined,
    ]),
  );

  const selectedSessionId = matchPath(
    { path: '/agent/:sessionId', end: true },
    location.pathname,
  )?.params.sessionId;

  if (collapsed) {
    return null;
  }

  const selectUser = () => {
    const nextUserId = userDraft.trim();
    if (!nextUserId) {
      setUserError('请输入 User ID');
      return;
    }
    setUserError('');
    if (nextUserId !== workspace.userId) {
      workspace.switchUser(nextUserId);
    }
    navigate('/agent');
  };

  const createSession = () => {
    workspace.newSession();
    navigate('/agent');
  };

  const openSession = (session: ConversationSessionSummaryResponse) => {
    workspace.updateWorkspace({
      sessionId: session.session_id,
      projectId: session.project_id ?? '',
    });
    navigate(`/agent/${encodeURIComponent(session.session_id)}`);
  };

  return (
    <div className="conversation-sidebar">
      <div className="sidebar-user-picker">
        <Typography.Text className="sidebar-section-label">
          当前用户
        </Typography.Text>
        <Input.Search
          aria-label="全局 User ID"
          value={userDraft}
          status={userError ? 'error' : undefined}
          onChange={(event) => {
            setUserDraft(event.target.value);
            if (userError) setUserError('');
          }}
          onSearch={selectUser}
          enterButton="选择"
          placeholder="输入 User ID"
        />
        {userError ? <div className="sidebar-inline-error">{userError}</div> : null}
      </div>

      <div className="sidebar-conversation-heading">
        <div>
          <Typography.Text className="sidebar-section-label">
            历史对话
          </Typography.Text>
          <Typography.Text className="sidebar-section-count">
            {sessions.length}
          </Typography.Text>
        </div>
        <Button
          type="text"
          size="small"
          aria-label="新建 Session"
          icon={<PlusOutlined />}
          onClick={createSession}
        />
      </div>

      <div className="sidebar-conversation-list">
        {conversations.isPending ? (
          <Skeleton active paragraph={{ rows: 5 }} title={false} />
        ) : conversations.isError ? (
          <div className="sidebar-query-state">
            <Typography.Text>{readableError(conversations.error)}</Typography.Text>
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => void conversations.refetch()}
            >
              重试
            </Button>
          </div>
        ) : sessions.length ? (
          <>
            {sessions.map((session) => {
              const projectName = session.project_id
                ? projectNames.get(session.project_id)
                : undefined;
              const projectLabel = session.project_id
                ? projectName
                  ? `${projectName} · ${session.project_id}`
                  : session.project_id
                : '无项目';
              return (
                <button
                  type="button"
                  key={session.session_id}
                  className={
                    session.session_id === selectedSessionId
                      ? 'conversation-list-item conversation-list-item-active'
                      : 'conversation-list-item'
                  }
                  onClick={() => openSession(session)}
                >
                  <MessageOutlined className="conversation-list-icon" />
                  <span className="conversation-list-body">
                    <span className="conversation-list-title" title={session.title || session.session_id}>
                      {session.title || session.session_id}
                    </span>
                    <span className="conversation-list-project" title={projectLabel}>
                      {projectLabel}
                    </span>
                    <span className="conversation-list-meta">
                      <span>{formatDate(session.last_message_at || session.updated_at)}</span>
                      <Tag color={session.session_status === 'archived' ? 'default' : 'blue'}>
                        {session.session_status === 'archived' ? '已归档' : '活跃'}
                      </Tag>
                    </span>
                  </span>
                </button>
              );
            })}
            {conversations.hasNextPage ? (
              <Button
                block
                className="sidebar-load-more"
                loading={conversations.isFetchingNextPage}
                onClick={() => void conversations.fetchNextPage()}
              >
                加载更多
              </Button>
            ) : null}
          </>
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="当前用户还没有历史对话"
          />
        )}
      </div>

      <Space className="sidebar-footnote" size="small">
        本地开发调试台
      </Space>
    </div>
  );
}
