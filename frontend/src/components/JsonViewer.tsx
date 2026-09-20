import { CheckOutlined, CopyOutlined } from '@ant-design/icons';
import { Button, message } from 'antd';
import { useState } from 'react';

interface JsonViewerProps {
  value: unknown;
  label?: string;
}

export function JsonViewer({ value, label = '复制 JSON' }: JsonViewerProps) {
  const [copied, setCopied] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();
  const json = JSON.stringify(value, null, 2);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      void messageApi.success('已复制到剪贴板');
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      void messageApi.error('复制失败，请手动选择文本');
    }
  };

  return (
    <div className="json-viewer">
      {contextHolder}
      <Button
        className="json-copy"
        icon={copied ? <CheckOutlined /> : <CopyOutlined />}
        onClick={copy}
        size="small"
      >
        {label}
      </Button>
      <pre>{json}</pre>
    </div>
  );
}
