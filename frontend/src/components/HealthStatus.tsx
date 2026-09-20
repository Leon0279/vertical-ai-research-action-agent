import { CloudServerOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Badge, Descriptions, Popover, Space, Tag, Typography } from 'antd';

import { api } from '../api/services';

export function HealthStatus() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => api.health(signal),
    refetchInterval: 30_000,
    retry: 1,
  });
  const readiness = useQuery({
    queryKey: ['readiness'],
    queryFn: ({ signal }) => api.readiness(signal),
    refetchInterval: 30_000,
    retry: 1,
  });

  const loading = health.isPending || readiness.isPending;
  const online = health.data?.status === 'ok';
  const ready = readiness.data?.status === 'ready';
  const status = loading ? 'processing' : ready ? 'success' : online ? 'warning' : 'error';
  const label = loading
    ? '检查服务'
    : ready
      ? '服务就绪'
      : online
        ? '依赖异常'
        : '服务离线';

  const content = (
    <div className="health-popover">
      <Descriptions column={1} size="small" colon={false}>
        <Descriptions.Item label="API 进程">
          <Tag color={online ? 'success' : 'error'}>{online ? '正常' : '不可用'}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="依赖状态">
          <Tag color={ready ? 'success' : 'warning'}>
            {ready ? '就绪' : readiness.data?.status ?? '未知'}
          </Tag>
        </Descriptions.Item>
      </Descriptions>
      {readiness.data?.checks ? (
        <Space direction="vertical" size={4}>
          {Object.entries(readiness.data.checks).map(([name, value]) => (
            <Badge
              key={name}
              status={value === 'ok' ? 'success' : 'error'}
              text={
                <Typography.Text code>
                  {name}: {value}
                </Typography.Text>
              }
            />
          ))}
        </Space>
      ) : null}
    </div>
  );

  return (
    <Popover content={content} title="运行状态" trigger="click">
      <Tag icon={<CloudServerOutlined />} color={status} className="health-tag">
        {label}
      </Tag>
    </Popover>
  );
}
