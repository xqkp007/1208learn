import React, { useMemo, useState } from 'react';
import { Card, DatePicker, Divider, InputNumber, Space, Typography, Button, message } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import { apiClient } from '@/api/client';

const { Title, Text, Paragraph } = Typography;
const { RangePicker } = DatePicker;

interface TriggerJobResponse {
  jobId: string;
  message: string;
}

export const InternalTasksPage: React.FC = () => {
  const [range, setRange] = useState<[Dayjs, Dayjs]>(() => {
    const yesterday = dayjs().subtract(1, 'day');
    return [yesterday.startOf('day'), yesterday.endOf('day')];
  });
  const [aggLoading, setAggLoading] = useState(false);
  const [extLoading, setExtLoading] = useState(false);
  const [compareSyncLoading, setCompareSyncLoading] = useState(false);
  const [limit, setLimit] = useState<number | null>(null);

  const startTime = useMemo(() => range[0].startOf('day').toISOString(), [range]);
  const endTime = useMemo(() => range[1].endOf('day').toISOString(), [range]);

  const triggerAggregation = async () => {
    setAggLoading(true);
    try {
      const { data } = await apiClient.post<TriggerJobResponse>(
        '/api/v1.10/admin/trigger-aggregation',
        { startTime, endTime },
        { timeout: 30_000 },
      );
      message.success(`${data.message} jobId=${data.jobId}`);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '触发数据预处理失败');
    } finally {
      setAggLoading(false);
    }
  };

  const triggerExtraction = async () => {
    setExtLoading(true);
    try {
      const payload = limit ? { limit } : {};
      const { data } = await apiClient.post<TriggerJobResponse>(
        '/api/v1.10/admin/trigger-extraction',
        payload,
        { timeout: 30_000 },
      );
      message.success(`${data.message} jobId=${data.jobId}`);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '触发AI提取失败');
    } finally {
      setExtLoading(false);
    }
  };

  const triggerCompareKbSync = async () => {
    setCompareSyncLoading(true);
    try {
      const { data } = await apiClient.post<TriggerJobResponse>(
        '/api/v1.10/admin/trigger-compare-kb-sync',
        {},
        { timeout: 30_000 },
      );
      message.success(`${data.message} jobId=${data.jobId}`);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '触发审核区知识库同步失败');
    } finally {
      setCompareSyncLoading(false);
    }
  };

  return (
    <div>
      <Title level={2} style={{ marginBottom: 8 }}>
        系统管理
      </Title>
      <Paragraph type="secondary" style={{ marginBottom: 16 }}>
        后台任务触发（内部测试页）
      </Paragraph>

      <Card title="数据预处理与聚合" bordered={false}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Text>选择处理日期范围：</Text>
            <div style={{ marginTop: 8 }}>
              <RangePicker
                allowClear={false}
                value={range}
                onChange={(value) => {
                  if (!value || !value[0] || !value[1]) return;
                  setRange([value[0], value[1]]);
                }}
              />
            </div>
          </div>
          <div>
            <Button type="primary" loading={aggLoading} onClick={triggerAggregation}>
              执行数据预处理
            </Button>
          </div>
          <Text type="secondary">
            点击后将按日期范围逐日执行数据预处理任务（可能耗时较长）。
          </Text>
        </Space>
      </Card>

      <Divider />

      <Card title="AI自动化提取" bordered={false}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Text type="secondary">
            点击后将处理当前所有已准备好的对话并生成待审核FAQ。
          </Text>
          <Space wrap>
            <Text>limit（可选）：</Text>
            <InputNumber
              min={1}
              max={1000}
              value={limit}
              placeholder="不填表示全部"
              onChange={(v) => setLimit(v ?? null)}
            />
          </Space>
          <div>
            <Button type="primary" loading={extLoading} onClick={triggerExtraction}>
              执行AI提取
            </Button>
          </div>
        </Space>
      </Card>

      <Divider />

      <Card title="审核区知识库同步" bordered={false}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Text type="secondary">
            仅同步“可见待审核”的Q+A到对比审核知识库（全量覆盖）。
          </Text>
          <div>
            <Button type="primary" loading={compareSyncLoading} onClick={triggerCompareKbSync}>
              执行同步
            </Button>
          </div>
        </Space>
      </Card>
    </div>
  );
};
