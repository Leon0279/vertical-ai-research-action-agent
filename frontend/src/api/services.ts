import './client';

import {
  createProjectV1ProjectsPost,
  getMemorySummaryV1MemoriesSummaryGet,
  getProjectV1ProjectsProjectIdGet,
  getSessionMemoryV1MemoriesSessionsSessionIdGet,
  healthHealthzGet,
  listActionMemoriesV1MemoriesActionsGet,
  listConversationMessagesV1ConversationsSessionIdMessagesGet,
  listConversationsV1ConversationsGet,
  listDecisionMemoriesV1MemoriesDecisionsGet,
  listPolicyMemoriesV1MemoriesPoliciesGet,
  listProjectIdsV1ProjectsGet,
  listResearchKnowledgeMemoriesV1MemoriesResearchKnowledgeGet,
  readinessReadyzGet,
  runAgentV1AgentRunPost,
} from './generated/sdk.gen';
import type {
  ActionMemoryListResponse,
  AgentRunRequest,
  AgentRunResponse,
  CreateProjectRequest,
  CreateProjectResponse,
  DecisionMemoryListResponse,
  ConversationMessageListResponse,
  ConversationSessionListResponse,
  HealthResponse,
  ListProjectIdsResponse,
  MemorySummaryResponse,
  PolicyMemoryListResponse,
  ProjectDetailsResponse,
  ReadinessResponse,
  ResearchKnowledgeMemoryListResponse,
  SessionMemoryResponse,
} from './generated/types.gen';
import { toApiError, unwrapApiResult } from './errors';

export type ActionStatus =
  | 'todo'
  | 'in_progress'
  | 'blocked'
  | 'done'
  | 'cancelled';

export type VisibilityScope = 'user' | 'project' | 'domain' | 'global';

export const api = {
  async health(signal?: AbortSignal): Promise<HealthResponse> {
    return unwrapApiResult<HealthResponse>(await healthHealthzGet({ signal }));
  },

  async readiness(signal?: AbortSignal): Promise<ReadinessResponse> {
    const result = await readinessReadyzGet({ signal });
    if (result.data !== undefined) {
      return result.data;
    }
    if (
      result.response?.status === 503 &&
      typeof result.error === 'object' &&
      result.error !== null &&
      'status' in result.error
    ) {
      return result.error as ReadinessResponse;
    }
    throw toApiError(result.error, result.response);
  },

  async runAgent(
    body: AgentRunRequest,
    signal?: AbortSignal,
  ): Promise<AgentRunResponse> {
    return unwrapApiResult<AgentRunResponse>(
      await runAgentV1AgentRunPost({ body, signal }),
    );
  },

  async listConversations(
    userId: string,
    cursor?: string,
    signal?: AbortSignal,
  ): Promise<ConversationSessionListResponse> {
    return unwrapApiResult<ConversationSessionListResponse>(
      await listConversationsV1ConversationsGet({
        query: { user_id: userId, limit: 20, cursor },
        signal,
      }),
    );
  },

  async listConversationMessages(
    userId: string,
    sessionId: string,
    cursor?: string,
    signal?: AbortSignal,
  ): Promise<ConversationMessageListResponse> {
    return unwrapApiResult<ConversationMessageListResponse>(
      await listConversationMessagesV1ConversationsSessionIdMessagesGet({
        path: { session_id: sessionId },
        query: { user_id: userId, limit: 50, cursor },
        signal,
      }),
    );
  },

  async listProjects(
    userId: string,
    signal?: AbortSignal,
  ): Promise<ListProjectIdsResponse> {
    return unwrapApiResult<ListProjectIdsResponse>(
      await listProjectIdsV1ProjectsGet({
        query: { user_id: userId },
        signal,
      }),
    );
  },

  async createProject(
    body: CreateProjectRequest,
    signal?: AbortSignal,
  ): Promise<CreateProjectResponse> {
    return unwrapApiResult<CreateProjectResponse>(
      await createProjectV1ProjectsPost({ body, signal }),
    );
  },

  async getProject(
    userId: string,
    projectId: string,
    signal?: AbortSignal,
  ): Promise<ProjectDetailsResponse> {
    return unwrapApiResult<ProjectDetailsResponse>(
      await getProjectV1ProjectsProjectIdGet({
        path: { project_id: projectId },
        query: { user_id: userId },
        signal,
      }),
    );
  },

  async memorySummary(
    userId: string,
    projectId: string,
    signal?: AbortSignal,
  ): Promise<MemorySummaryResponse> {
    return unwrapApiResult<MemorySummaryResponse>(
      await getMemorySummaryV1MemoriesSummaryGet({
        query: { user_id: userId, project_id: projectId },
        signal,
      }),
    );
  },

  async decisions(
    userId: string,
    projectId: string,
    cursor?: string,
    signal?: AbortSignal,
  ): Promise<DecisionMemoryListResponse> {
    return unwrapApiResult<DecisionMemoryListResponse>(
      await listDecisionMemoriesV1MemoriesDecisionsGet({
        query: {
          user_id: userId,
          project_id: projectId,
          limit: 20,
          cursor,
        },
        signal,
      }),
    );
  },

  async actions(
    userId: string,
    projectId: string,
    statuses: ActionStatus[],
    cursor?: string,
    signal?: AbortSignal,
  ): Promise<ActionMemoryListResponse> {
    return unwrapApiResult<ActionMemoryListResponse>(
      await listActionMemoriesV1MemoriesActionsGet({
        query: {
          user_id: userId,
          project_id: projectId,
          action_status: statuses.length ? statuses : undefined,
          limit: 20,
          cursor,
        },
        signal,
      }),
    );
  },

  async policies(
    userId: string,
    projectId: string,
    cursor?: string,
    signal?: AbortSignal,
  ): Promise<PolicyMemoryListResponse> {
    return unwrapApiResult<PolicyMemoryListResponse>(
      await listPolicyMemoriesV1MemoriesPoliciesGet({
        query: {
          user_id: userId,
          project_id: projectId,
          limit: 20,
          cursor,
        },
        signal,
      }),
    );
  },

  async researchKnowledge(
    userId: string,
    projectId: string,
    scopes: VisibilityScope[],
    cursor?: string,
    signal?: AbortSignal,
  ): Promise<ResearchKnowledgeMemoryListResponse> {
    return unwrapApiResult<ResearchKnowledgeMemoryListResponse>(
      await listResearchKnowledgeMemoriesV1MemoriesResearchKnowledgeGet({
        query: {
          user_id: userId,
          project_id: projectId,
          visibility_scope: scopes.length ? scopes : undefined,
          limit: 20,
          cursor,
        },
        signal,
      }),
    );
  },

  async sessionMemory(
    userId: string,
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<SessionMemoryResponse> {
    return unwrapApiResult<SessionMemoryResponse>(
      await getSessionMemoryV1MemoriesSessionsSessionIdGet({
        path: { session_id: sessionId },
        query: { user_id: userId },
        signal,
      }),
    );
  },
};
