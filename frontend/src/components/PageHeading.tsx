import { Typography } from 'antd';
import type { ReactNode } from 'react';

interface PageHeadingProps {
  title: string;
  description: string;
  extra?: ReactNode;
}

export function PageHeading({ title, description, extra }: PageHeadingProps) {
  return (
    <div className="page-heading">
      <div>
        <Typography.Title level={2}>{title}</Typography.Title>
        <Typography.Paragraph type="secondary">
          {description}
        </Typography.Paragraph>
      </div>
      {extra ? <div className="page-heading-extra">{extra}</div> : null}
    </div>
  );
}
