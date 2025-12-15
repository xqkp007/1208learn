import React, { useEffect, useState } from 'react';
import {
  Card,
  Table,
  Button,
  Input,
  Space,
  Typography,
  Statistic,
  Row,
  Col,
  Drawer,
  Form,
  Modal,
  message,
  Empty,
  Tag,
  Descriptions,
} from 'antd';
import {
  SearchOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { TableRowSelection } from 'antd/es/table/interface';
import { apiClient } from '@/api/client';
import { useAuthStore } from '@/store/auth';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

interface PendingFAQ {
  id: number;
  question: string;
  answer: string;
  source_call_id?: string | null;
  source_conversation_text?: string | null;
}

interface PendingFAQListResponse {
  total: number;
  page: number;
  pageSize: number;
  items: PendingFAQ[];
}

const BULK_LIMIT = 100;

export const ReviewWorkbenchPage: React.FC = () => {
  const [keyword, setKeyword] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<PendingFAQ[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [bulkAction, setBulkAction] = useState<'accept' | 'discard' | null>(null);

  const [drawerVisible, setDrawerVisible] = useState(false);
  const [editingFaq, setEditingFaq] = useState<PendingFAQ | null>(null);
  const [form] = Form.useForm();

  const user = useAuthStore((s) => s.user);
  const scenarioName = user?.scenarioId === 1 ? '水务知识库' : '公交知识库';

  useEffect(() => {
    setSelectedRowKeys((prev) =>
      prev.filter((key) => data.some((item) => item.id === key)),
    );
  }, [data]);

  const loadData = async () => {
    setLoading(true);
    try {
      const { data: response } = await apiClient.get<PendingFAQListResponse>(
        '/api/v1.4/pending-faqs',
        {
          params: {
            page,
            pageSize,
            keyword: keyword || undefined,
          },
        },
      );
      setData(response.items);
      setTotal(response.total);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize]);

  const handleSearch = () => {
    setPage(1);
    void loadData();
  };

  const handleReset = () => {
    setKeyword('');
    setPage(1);
    void loadData();
  };

  const getSelectedFaqs = () =>
    data.filter((item) => selectedRowKeys.includes(item.id));

  const executeBulkAction = async (
    type: 'accept' | 'discard',
    targets: PendingFAQ[],
  ) => {
    if (!user?.scenarioId) {
      message.error('缺少场景信息，无法执行操作');
      throw new Error('missing scenario');
    }

    setBulkAction(type);
    try {
      if (type === 'accept') {
        await apiClient.post('/api/v1.8/knowledge-items/bulk-create', {
          items: targets.map((item) => ({
            pendingFaqId: item.id,
            scenarioId: user.scenarioId,
            question: item.question,
            answer: item.answer,
          })),
        });
        message.success(`${targets.length} 条 FAQ 采纳成功`);
      } else {
        await apiClient.post('/api/v1.8/pending-faqs/bulk-discard', {
          pendingFaqIds: targets.map((item) => item.id),
        });
        message.success(`${targets.length} 条 FAQ 废弃成功`);
      }

      setData((prev) => prev.filter((item) => !targets.some((faq) => faq.id === item.id)));
      setSelectedRowKeys((prev) =>
        prev.filter((key) => !targets.some((faq) => faq.id === key)),
      );
      setTotal((prev) => Math.max(0, prev - targets.length));
    } catch (error) {
      message.error(
        (error as any)?.response?.data?.detail ||
          `批量${type === 'accept' ? '采纳' : '废弃'}失败，请稍后重试`,
      );
    } finally {
      setBulkAction(null);
    }
  };

  const handleBulkActionRequest = (type: 'accept' | 'discard') => {
    const targets = getSelectedFaqs();
    if (!targets.length) {
      message.warning('请先选择至少一条 FAQ');
      return;
    }
    if (targets.length > BULK_LIMIT) {
      message.warning(`单次最多只能处理 ${BULK_LIMIT} 条 FAQ`);
      return;
    }

    Modal.confirm({
      title: type === 'accept' ? '确认批量采纳' : '确认批量废弃',
      content: `您确定要${type === 'accept' ? '采纳' : '废弃'}这 ${
        targets.length
      } 条 FAQ 吗？`,
      okText: type === 'accept' ? '确认采纳' : '确认废弃',
      okType: type === 'accept' ? 'primary' : 'danger',
      cancelText: '取消',
      onOk: () => executeBulkAction(type, targets),
    });
  };

  const openEditDrawer = (faq: PendingFAQ) => {
    setEditingFaq(faq);
    form.setFieldsValue({
      question: faq.question,
      answer: faq.answer,
    });
    setDrawerVisible(true);
  };

  const closeDrawer = () => {
    setDrawerVisible(false);
    setEditingFaq(null);
    form.resetFields();
  };

  const removeFromList = (id: number) => {
    setData((prev) => prev.filter((item) => item.id !== id));
    setSelectedRowKeys((prev) => prev.filter((key) => key !== id));
    setTotal((prev) => Math.max(0, prev - 1));
  };

  const handleAccept = async (faq: PendingFAQ, edited: boolean = false) => {
    let question = faq.question;
    let answer = faq.answer;

    if (edited) {
      try {
        const values = await form.validateFields();
        question = values.question.trim();
        answer = values.answer.trim();
      } catch {
        return;
      }
    }

    if (!question || !answer) {
      message.warning('问题和答案不能为空');
      return;
    }

    try {
      await apiClient.post('/api/v1.4/knowledge-items', {
        pendingFaqId: faq.id,
        scenarioId: user?.scenarioId,
        question,
        answer,
      });
      message.success('采纳成功');
      removeFromList(faq.id);
      closeDrawer();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '采纳失败，请稍后重试');
    }
  };

  const handleDiscard = (faq: PendingFAQ) => {
    Modal.confirm({
      title: '确认废弃',
      content: '确认废弃该条 FAQ 吗？废弃后将无法恢复。',
      okText: '确认废弃',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await apiClient.delete(`/api/v1.4/pending-faqs/${faq.id}`);
          message.success('废弃成功');
          removeFromList(faq.id);
        } catch (error: any) {
          message.error(error?.response?.data?.detail || '废弃失败，请稍后重试');
        }
      },
    });
  };

  const columns: ColumnsType<PendingFAQ> = [
    {
      title: '序号',
      key: 'index',
      width: 80,
      align: 'center',
      render: (_, __, index) => (page - 1) * pageSize + index + 1,
    },
    {
      title: '问题',
      dataIndex: 'question',
      key: 'question',
      width: '35%',
      ellipsis: true,
    },
    {
      title: '答案',
      dataIndex: 'answer',
      key: 'answer',
      width: '40%',
      render: (text) => (
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {text || <Text type="secondary">暂无答案</Text>}
        </div>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 240,
      align: 'center',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="primary"
            size="small"
            icon={<CheckCircleOutlined />}
            onClick={() => handleAccept(record)}
          >
            采纳
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEditDrawer(record)}
          >
            修改
          </Button>
          <Button
            danger
            size="small"
            icon={<CloseCircleOutlined />}
            onClick={() => handleDiscard(record)}
          >
            废弃
          </Button>
        </Space>
      ),
    },
  ];

  const rowSelection: TableRowSelection<PendingFAQ> = {
    selectedRowKeys,
    onChange: (keys) => setSelectedRowKeys(keys),
    preserveSelectedRowKeys: true,
  };

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card size="small">
            <Statistic
              title="当前场景"
              value={scenarioName}
              valueStyle={{ fontSize: 18 }}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small">
            <Statistic
              title="待审核总数"
              value={total}
              valueStyle={{ color: '#1890ff', fontSize: 18 }}
              suffix="条"
            />
          </Card>
        </Col>
      </Row>

      <Card bordered={false} size="small">
        <Space style={{ marginBottom: 16 }} size="middle">
          <Input
            placeholder="搜索问题或答案关键词..."
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 300 }}
            allowClear
          />
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={handleSearch}
            loading={loading}
          >
            搜索
          </Button>
          <Button icon={<ReloadOutlined />} onClick={handleReset}>
            重置
          </Button>
        </Space>

        {selectedRowKeys.length > 0 && (
          <div className="bulk-action-bar">
            <div className="selected-count">
              已选择 {selectedRowKeys.length} 项
            </div>
            <Space size="middle">
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                loading={bulkAction === 'accept'}
                onClick={() => handleBulkActionRequest('accept')}
              >
                批量采纳
              </Button>
              <Button
                danger
                icon={<CloseCircleOutlined />}
                loading={bulkAction === 'discard'}
                onClick={() => handleBulkActionRequest('discard')}
              >
                批量废弃
              </Button>
            </Space>
          </div>
        )}

        <Table
          columns={columns}
          dataSource={data}
          rowKey="id"
          rowSelection={rowSelection}
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条记录`,
            onChange: (newPage, newPageSize) => {
              setPage(newPage);
              if (newPageSize !== pageSize) {
                setPageSize(newPageSize);
                setPage(1);
              }
            },
          }}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <Space direction="vertical" align="center">
                    <Text>太棒了！所有 FAQ 都已审核完成</Text>
                    <Text type="secondary">暂无待审核的 FAQ，请稍后再来查看</Text>
                  </Space>
                }
              />
            ),
          }}
        />
      </Card>

      <Drawer
        title="编辑并审核 FAQ"
        width={800}
        open={drawerVisible}
        onClose={closeDrawer}
        extra={
          <Space>
            <Button onClick={closeDrawer}>取消</Button>
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              onClick={() => editingFaq && handleAccept(editingFaq, true)}
            >
              保存并采纳
            </Button>
          </Space>
        }
      >
        {editingFaq && (
          <>
            <Form form={form} layout="vertical">
              <Form.Item
                label="问题"
                name="question"
                rules={[{ required: true, message: '请输入问题' }]}
              >
                <Input placeholder="请输入问题内容" />
              </Form.Item>
              <Form.Item
                label="答案"
                name="answer"
                rules={[{ required: true, message: '请输入答案' }]}
              >
                <TextArea
                  rows={8}
                  placeholder="请输入答案内容"
                  showCount
                />
              </Form.Item>
            </Form>

            <Card
              title="原始对话参考"
              size="small"
              style={{ marginTop: 24 }}
              type="inner"
            >
              <Descriptions column={1} size="small">
                <Descriptions.Item label="对话 ID">
                  <Tag>{editingFaq.source_call_id || editingFaq.id}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="对话内容">
                  <Text style={{ whiteSpace: 'pre-wrap' }}>
                    {editingFaq.source_conversation_text || '暂无对话内容'}
                  </Text>
                </Descriptions.Item>
              </Descriptions>
            </Card>
          </>
        )}
      </Drawer>
    </div>
  );
};
