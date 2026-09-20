export class ApiError extends Error {
  readonly status?: number;
  readonly code?: string;
  readonly details: string[];
  readonly payload: unknown;

  constructor(
    message: string,
    options: {
      status?: number;
      code?: string;
      details?: string[];
      payload?: unknown;
    } = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = options.status;
    this.code = options.code;
    this.details = options.details ?? [];
    this.payload = options.payload;
  }
}

type ApiResult<T> =
  | {
      data: T;
      error: undefined;
      response?: Response;
    }
  | {
      data: undefined;
      error: unknown;
      response?: Response;
    };

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

function validationDetails(payload: unknown): string[] {
  if (!isRecord(payload) || !Array.isArray(payload.detail)) {
    return [];
  }

  return payload.detail.flatMap((item) => {
    if (!isRecord(item)) {
      return [];
    }
    const location = Array.isArray(item.loc) ? item.loc.join('.') : 'request';
    const message = typeof item.msg === 'string' ? item.msg : '校验失败';
    return [`${location}: ${message}`];
  });
}

export function toApiError(payload: unknown, response?: Response): ApiError {
  if (payload instanceof ApiError) {
    return payload;
  }
  if (payload instanceof DOMException && payload.name === 'AbortError') {
    return new ApiError('请求已取消', { code: 'REQUEST_ABORTED', payload });
  }

  const details = validationDetails(payload);
  if (isRecord(payload)) {
    const code =
      typeof payload.error_code === 'string' ? payload.error_code : undefined;
    const reason =
      typeof payload.error_reason === 'string'
        ? payload.error_reason
        : details[0];
    return new ApiError(
      reason ?? `请求失败${response ? `（HTTP ${response.status}）` : ''}`,
      {
        status: response?.status,
        code,
        details,
        payload,
      },
    );
  }

  if (payload instanceof Error) {
    return new ApiError(payload.message, {
      status: response?.status,
      payload,
    });
  }

  return new ApiError(
    `请求失败${response ? `（HTTP ${response.status}）` : ''}`,
    { status: response?.status, details, payload },
  );
}

export function unwrapApiResult<T>(result: ApiResult<T>): T {
  if (result.data !== undefined) {
    return result.data;
  }
  throw toApiError(result.error, result.response);
}

export function readableError(error: unknown): string {
  if (error instanceof ApiError) {
    const suffix = [
      error.status ? `HTTP ${error.status}` : undefined,
      error.code,
    ]
      .filter(Boolean)
      .join(' · ');
    return suffix ? `${error.message}（${suffix}）` : error.message;
  }
  return error instanceof Error ? error.message : '发生未知错误';
}
