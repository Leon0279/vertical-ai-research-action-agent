import { Alert } from 'antd';

import { ApiError, readableError } from '../api/errors';

export function RequestError({ error }: { error: unknown }) {
  const details = error instanceof ApiError ? error.details : [];
  return (
    <Alert
      type="error"
      showIcon
      title="请求失败"
      description={
        <div>
          <div>{readableError(error)}</div>
          {details.length > 1 ? (
            <ul>
              {details.slice(1).map((detail) => (
                <li key={detail}>{detail}</li>
              ))}
            </ul>
          ) : null}
        </div>
      }
    />
  );
}
