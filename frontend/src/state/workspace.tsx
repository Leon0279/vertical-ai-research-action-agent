/* eslint-disable react-refresh/only-export-components */

import {
  createContext,
  type PropsWithChildren,
  useContext,
  useMemo,
  useState,
} from 'react';

const STORAGE_KEY = 'vaa.debug.workspace.v1';

export interface WorkspaceState {
  userId: string;
  projectId: string;
  sessionId: string;
  iterationBudget: number;
}

interface WorkspaceContextValue extends WorkspaceState {
  updateWorkspace: (patch: Partial<WorkspaceState>) => void;
  newSession: () => void;
}

const createSessionId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const defaultWorkspace = (): WorkspaceState => ({
  userId: 'local-demo',
  projectId: '',
  sessionId: createSessionId(),
  iterationBudget: 2,
});

function readWorkspace(): WorkspaceState {
  const fallback = defaultWorkspace();
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return fallback;
    }
    const parsed = JSON.parse(stored) as Partial<WorkspaceState>;
    return {
      userId:
        typeof parsed.userId === 'string' && parsed.userId.trim()
          ? parsed.userId
          : fallback.userId,
      projectId:
        typeof parsed.projectId === 'string' ? parsed.projectId : '',
      sessionId:
        typeof parsed.sessionId === 'string' && parsed.sessionId.trim()
          ? parsed.sessionId
          : fallback.sessionId,
      iterationBudget:
        typeof parsed.iterationBudget === 'number' &&
        parsed.iterationBudget >= 1 &&
        parsed.iterationBudget <= 5
          ? parsed.iterationBudget
          : fallback.iterationBudget,
    };
  } catch {
    return fallback;
  }
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: PropsWithChildren) {
  const [workspace, setWorkspace] = useState<WorkspaceState>(readWorkspace);

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      ...workspace,
      updateWorkspace: (patch) => {
        setWorkspace((current) => {
          const next = { ...current, ...patch };
          localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
          return next;
        });
      },
      newSession: () => {
        setWorkspace((current) => {
          const next = { ...current, sessionId: createSessionId() };
          localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
          return next;
        });
      },
    }),
    [workspace],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceContextValue {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error('useWorkspace must be used inside WorkspaceProvider');
  }
  return context;
}
