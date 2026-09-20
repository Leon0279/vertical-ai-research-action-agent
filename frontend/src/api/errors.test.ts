import { describe, expect, it } from 'vitest';

import { ApiError, readableError, unwrapApiResult } from './errors';

describe('API error normalization', () => {
  it('preserves stable backend error codes and status', () => {
    expect(() =>
      unwrapApiResult({
        data: undefined,
        error: {
          error_code: 'PROJECT_NOT_FOUND',
          error_reason: '项目不存在',
        },
        response: new Response(null, { status: 404 }),
      }),
    ).toThrowError('项目不存在');

    try {
      unwrapApiResult({
        data: undefined,
        error: {
          error_code: 'PROJECT_NOT_FOUND',
          error_reason: '项目不存在',
        },
        response: new Response(null, { status: 404 }),
      });
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect(readableError(error)).toContain('HTTP 404 · PROJECT_NOT_FOUND');
    }
  });

  it('turns FastAPI validation details into readable field paths', () => {
    try {
      unwrapApiResult({
        data: undefined,
        error: {
          detail: [
            {
              loc: ['body', 'query'],
              msg: 'Field required',
              type: 'missing',
            },
          ],
        },
        response: new Response(null, { status: 422 }),
      });
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).details).toEqual([
        'body.query: Field required',
      ]);
    }
  });
});
