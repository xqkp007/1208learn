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
  Modal,
  Form,
  Tabs,
  message,
  Tag,
  Divider,
} from 'antd';
import {
  SearchOutlined,
  ReloadOutlined,
  EditOutlined,
  StopOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { apiClient } from '@/api/client';
import { useAuthStore } from '@/store/auth';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

interface KnowledgeItem {
  id: number;
  question: string;
  answer: string;
  status: string;
  updatedAt: string;
}

interface KnowledgeListResponse {
  total: number;
  page: number;
  pageSize: number;
  items: KnowledgeItem[];
}

interface KnowledgeDetailResponse {
  id: number;
  question: string;
  answer: string;
  status: string;
  updatedAt: string;
}

interface ScenarioSyncResult {
  scenarioId: number;
  items: number;
  status: string;
  message: string;
}

const formatDateTime = (value: string) => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', { hour12: false });
};

export const KnowledgeManagementPage: React.FC = () => {
  const [statusTab, setStatusTab] = useState<'active' | 'disabled'>('active');
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [tabCounts, setTabCounts] = useState<{ active: number; disabled: number }>({
    active: 0,
    disabled: 0,
  });
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const [modalVisible, setModalVisible] = useState(false);
  const [editingItemId, setEditingItemId] = useState<number | null>(null);
  const [form] = Form.useForm();

  const user = useAuthStore((s) => s.user);
  const scenarioName = user?.scenarioId === 1 ? '水务知识库' : '公交知识库';

  const loadCounts = async () => {
    try {
      const [activeResp, disabledResp] = await Promise.all([
        apiClient.get<KnowledgeListResponse>('/api/v1.4.1/knowledge-items', {
          params: { status: 'active', page: 1, pageSize: 1 },
        }),
        apiClient.get<KnowledgeListResponse>('/api/v1.4.1/knowledge-items', {
          params: { status: 'disabled', page: 1, pageSize: 1 },
        }),
      ]);
      setTabCounts({
        active: activeResp.data.total,
        disabled: disabledResp.data.total,
      });
    } catch (error) {
      console.error('Failed to load counts', error);
    }
  };

  const loadList = async () => {
    setLoading(true);
    try {
      const { data } = await apiClient.get<KnowledgeListResponse>(
        '/api/v1.4.1/knowledge-items',
        {
          params: {
            status: statusTab,
            page,
            pageSize,
            keyword: keyword || undefined,
          },
        },
      );
      setItems(data.items);
      setTotal(data.total);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusTab, page, pageSize]);

  useEffect(() => {
    void loadCounts();
  }, []);

  const handleSearch = () => {
    setPage(1);
    void loadList();
  };

  const handleReset = () => {
    setKeyword('');
    setPage(1);
    void loadList();
  };

  const triggerSync = () => {
    if (!user?.scenarioId) {
      message.error('缺少场景信息，无法同步');
      return;
    }

    Modal.confirm({
      title: '确认同步',
      content: '您确定要将当前所有“已生效”的知识同步到知识库吗？',
      okText: '确认同步',
      okType: 'primary',
      cancelText: '取消',
      onOk: async () => {
        setSyncing(true);
        try {
          const { data } = await apiClient.post<ScenarioSyncResult>(
            `/api/v1.3/scenarios/${user.scenarioId}/trigger-sync`,
            undefined,
            { timeout: 15 * 60 * 1000 },
          );
          void data;
          message.success('同步成功');
        } catch (error: any) {
          const timeoutHint =
            error?.code === 'ECONNABORTED' || String(error?.message || '').toLowerCase().includes('timeout');
          const detail = error?.response?.data?.detail;
          message.error(
            timeoutHint ? '同步请求超时（15分钟）。' : detail || '同步失败，请稍后重试',
          );
        } finally {
          setSyncing(false);
        }
      },
    });
  };

  const openEditModal = async (itemId: number) => {
    try {
      const { data } = await apiClient.get<KnowledgeDetailResponse>(
        `/api/v1.4.1/knowledge-items/${itemId}`,
      );
      setEditingItemId(itemId);
      form.setFieldsValue({
        question: data.question,
        answer: data.answer,
      });
      setModalVisible(true);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '获取知识详情失败');
    }
  };

  const closeModal = () => {
    setModalVisible(false);
    setEditingItemId(null);
    form.resetFields();
  };

  const saveEdit = async () => {
    if (!editingItemId) return;

    try {
      const values = await form.validateFields();
      await apiClient.put(`/api/v1.4.1/knowledge-items/${editingItemId}`, {
        question: values.question.trim(),
        answer: values.answer.trim(),
      });
      message.success('更新成功');
      closeModal();
      await loadList();
      await loadCounts();
    } catch (error: any) {
      if (error?.response?.data?.detail || error?.message) {
        message.error(error?.response?.data?.detail || error?.message || '更新失败，请稍后重试');
      }
    }
  };

  const toggleStatus = (item: KnowledgeItem, nextStatus: 'active' | 'disabled') => {
    const action = nextStatus === 'disabled' ? '禁用' : '启用';
    Modal.confirm({
      title: `确认${action}`,
      content: `确认${action}该知识吗？`,
      okText: `确认${action}`,
      okType: nextStatus === 'disabled' ? 'danger' : 'primary',
      cancelText: '取消',
      onOk: async () => {
        try {
          await apiClient.put(`/api/v1.4.1/knowledge-items/${item.id}`, {
            status: nextStatus,
          });
          message.success(`${action}成功`);
          await loadList();
          await loadCounts();
        } catch (error: any) {
          message.error(error?.response?.data?.detail || `${action}失败，请稍后重试`);
        }
      },
    });
  };

  const columns: ColumnsType<KnowledgeItem> = [
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
      width: '30%',
      ellipsis: true,
    },
    {
      title: '答案',
      dataIndex: 'answer',
      key: 'answer',
      width: '35%',
      render: (text) => (
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {text || <Text type="secondary">—</Text>}
        </div>
      ),
    },
    {
      title: '最后更新',
      dataIndex: 'updatedAt',
      key: 'updatedAt',
      width: 180,
      render: (text) => formatDateTime(text),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      align: 'center',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="primary"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEditModal(record.id)}
          >
            编辑
          </Button>
          {statusTab === 'active' ? (
            <Button
              danger
              size="small"
              icon={<StopOutlined />}
              onClick={() => toggleStatus(record, 'disabled')}
            >
              禁用
            </Button>
          ) : (
            <Button
              type="primary"
              size="small"
              icon={<CheckCircleOutlined />}
              onClick={() => toggleStatus(record, 'active')}
            >
              启用
            </Button>
          )}
        </Space>
      ),
    },
  ];

  const tabItems = [
    {
      key: 'active',
      label: (
        <span>
          已生效 <Tag color="success">{tabCounts.active}</Tag>
        </span>
      ),
    },
    {
      key: 'disabled',
      label: (
        <span>
          已禁用 <Tag>{tabCounts.disabled}</Tag>
        </span>
      ),
    },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Card size="small">
            <Statistic
              title="当前知识库"
              value={scenarioName}
              valueStyle={{ fontSize: 18, color: '#1890ff' }}
            />
          </Card>
        </Col>
      </Row>

      <Card bordered={false} size="small">
        <Space style={{ marginBottom: 16 }} size="middle">
          <Input
            placeholder="按问题或答案关键词搜索..."
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
          <Divider type="vertical" style={{ height: '32px', borderColor: '#d9d9d9' }} />
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={triggerSync}
            loading={syncing}
            disabled={syncing}
          >
            {syncing ? '同步中...' : '立即同步至知识库'}
          </Button>
        </Space>

        <Tabs
          activeKey={statusTab}
          items={tabItems}
          onChange={(key) => {
            setStatusTab(key as 'active' | 'disabled');
            setPage(1);
          }}
          style={{ marginBottom: 16 }}
        />

        <Table
          columns={columns}
          dataSource={items}
          rowKey="id"
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
        />
      </Card>

      <Modal
        title="编辑知识"
        open={modalVisible}
        onOk={saveEdit}
        onCancel={closeModal}
        width={700}
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 24 }}>
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
            <TextArea rows={10} placeholder="请输入答案内容" showCount />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
