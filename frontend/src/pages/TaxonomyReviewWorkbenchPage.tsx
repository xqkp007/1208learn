import React, { useEffect, useState } from 'react';
import {
  Button,
  Card,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Space,
  Table,
  Tabs,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/api/client';
import { useAuthStore } from '@/store/auth';

const { Title, Text } = Typography;
const { TextArea } = Input;

type ScopeCode = 'water' | 'bus' | 'bike';

interface ReviewPathSegment {
  level: number;
  name: string;
}

interface ReviewCase {
  id: number;
  content: string;
}

interface ReviewItem {
  id: number;
  scopeCode: ScopeCode;
  path: ReviewPathSegment[];
  definition: string;
  cases: ReviewCase[];
}

interface ReviewListResponse {
  items: ReviewItem[];
}

const scopeLabels: Record<ScopeCode, string> = {
  water: '水务',
  bus: '公交',
  bike: '自行车',
};

export const TaxonomyReviewWorkbenchPage: React.FC = () => {
  const user = useAuthStore((s) => s.user);
  const isBusUser = user?.scenarioId === 2;

  const [scope, setScope] = useState<ScopeCode>(isBusUser ? 'bus' : 'water');
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<ReviewItem | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [actionLoadingType, setActionLoadingType] = useState<'accept' | 'discard' | null>(null);
  const [form] = Form.useForm();

  const loadData = async (nextScope: ScopeCode = scope) => {
    setLoading(true);
    try {
      const { data } = await apiClient.get<ReviewListResponse>(
        '/api/v1.14/kb-taxonomy-review/pending',
        { params: { scope: nextScope } },
      );
      setItems(data.items || []);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '加载待审核列表失败');
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData(scope);
    setDrawerOpen(false);
    setEditingItem(null);
    form.resetFields();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope]);

  const getPathName = (segments: ReviewPathSegment[], level: number) =>
    segments.find((seg) => seg.level === level)?.name || '';

  const renderPath = (segments: ReviewPathSegment[]) =>
    segments.map((seg) => seg.name).join('/');

  const renderDefinition = (definition: string) => (
    <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
      {definition || <Text type="secondary">暂无定义</Text>}
    </div>
  );

  const renderCases = (cases: ReviewCase[]) => {
    if (!cases || cases.length === 0) {
      return <Text type="secondary">暂无案例</Text>;
    }
    return (
      <Space direction="vertical" size="small">
        {cases.map((item, index) => (
          <div key={item.id}>
            <Text type="secondary">案例 {index + 1}</Text>
            <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {item.content}
            </div>
          </div>
        ))}
      </Space>
    );
  };

  const removeFromList = (id: number) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
    if (editingItem?.id === id) {
      closeDrawer();
    }
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setEditingItem(null);
    form.resetFields();
  };

  const openEditDrawer = (item: ReviewItem) => {
    setEditingItem(item);
    form.setFieldsValue({
      l3Name: getPathName(item.path, 3),
      definition: item.definition,
      cases: item.cases.length ? item.cases.map((c) => c.content) : [''],
    });
    setDrawerOpen(true);
  };

  const normalizePayload = (
    l3Name: string,
    definition: string,
    cases: string[],
  ) => {
    const cleanName = (l3Name || '').trim();
    const cleanDefinition = (definition || '').trim();
    const cleanCases = (cases || []).map((c) => (c || '').trim());

    if (!cleanName) {
      message.warning('请输入三级分类名称');
      return null;
    }
    if (!cleanDefinition) {
      message.warning('请输入定义');
      return null;
    }
    if (cleanCases.length < 1) {
      message.warning('至少需要一条案例');
      return null;
    }
    if (cleanCases.some((c) => !c)) {
      message.warning('案例内容不能为空');
      return null;
    }

    return {
      l3Name: cleanName,
      definition: cleanDefinition,
      cases: cleanCases,
    };
  };

  const handleAccept = async (item: ReviewItem, edited: boolean) => {
    let payload;

    if (edited) {
      try {
        const values = await form.validateFields();
        payload = normalizePayload(values.l3Name, values.definition, values.cases || []);
      } catch {
        return;
      }
    } else {
      payload = normalizePayload(
        getPathName(item.path, 3),
        item.definition,
        item.cases.map((c) => c.content),
      );
    }

    if (!payload) {
      return;
    }

    setActionLoadingId(item.id);
    setActionLoadingType('accept');
    try {
      await apiClient.post(
        `/api/v1.14/kb-taxonomy-review/items/${item.id}/accept`,
        {
          scope,
          ...payload,
        },
      );
      message.success('采纳成功');
      removeFromList(item.id);
      closeDrawer();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '采纳失败，请稍后重试');
    } finally {
      setActionLoadingId(null);
      setActionLoadingType(null);
    }
  };

  const handleDiscard = (item: ReviewItem) => {
    Modal.confirm({
      title: '确认废弃',
      content: '确认废弃该条分类吗？废弃后将无法恢复。',
      okText: '确认废弃',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setActionLoadingId(item.id);
        setActionLoadingType('discard');
        try {
          await apiClient.post(
            `/api/v1.14/kb-taxonomy-review/items/${item.id}/discard`,
            null,
            { params: { scope } },
          );
          message.success('废弃成功');
          removeFromList(item.id);
        } catch (error: any) {
          message.error(error?.response?.data?.detail || '废弃失败，请稍后重试');
        } finally {
          setActionLoadingId(null);
          setActionLoadingType(null);
        }
      },
    });
  };

  const columns: ColumnsType<ReviewItem> = [
    {
      title: '三级分类(路径)',
      dataIndex: 'path',
      key: 'path',
      width: '22%',
      render: renderPath,
    },
    {
      title: '定义',
      dataIndex: 'definition',
      key: 'definition',
      width: '34%',
      render: renderDefinition,
    },
    {
      title: '案例',
      dataIndex: 'cases',
      key: 'cases',
      width: '36%',
      render: renderCases,
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
            icon={<CheckCircleOutlined />}
            loading={actionLoadingId === record.id && actionLoadingType === 'accept'}
            onClick={() => handleAccept(record, false)}
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
            loading={actionLoadingId === record.id && actionLoadingType === 'discard'}
            onClick={() => handleDiscard(record)}
          >
            废弃
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }} size="middle" align="center">
        <Title level={4} style={{ margin: 0 }}>
          三级分类审核工作台
        </Title>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => loadData(scope)}
          loading={loading}
        >
          刷新
        </Button>
      </Space>

      {isBusUser ? (
        <Tabs
          activeKey={scope}
          onChange={(key) => setScope(key as ScopeCode)}
          items={[
            { key: 'bus', label: scopeLabels.bus },
            { key: 'bike', label: scopeLabels.bike },
          ]}
          style={{ marginBottom: 12 }}
        />
      ) : null}

      <Card bordered={false} size="small">
        <Table
          columns={columns}
          dataSource={items}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <Space direction="vertical" align="center">
                    <Text>暂无待审核分类</Text>
                    <Text type="secondary">请稍后再来查看</Text>
                  </Space>
                }
              />
            ),
          }}
        />
      </Card>

      <Drawer
        title="编辑并审核三级分类"
        width={860}
        open={drawerOpen}
        onClose={closeDrawer}
        extra={
          <Space>
            <Button onClick={closeDrawer}>取消</Button>
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              loading={actionLoadingId === editingItem?.id && actionLoadingType === 'accept'}
              onClick={() => editingItem && handleAccept(editingItem, true)}
            >
              保存并采纳
            </Button>
          </Space>
        }
      >
        {editingItem && (
          <Form form={form} layout="vertical">
            <Form.Item label="一级分类">
              <Input value={getPathName(editingItem.path, 1)} disabled />
            </Form.Item>
            <Form.Item label="二级分类">
              <Input value={getPathName(editingItem.path, 2)} disabled />
            </Form.Item>
            <Form.Item
              label="三级名称"
              name="l3Name"
              rules={[{ required: true, message: '请输入三级分类名称' }]}
            >
              <Input placeholder="请输入三级分类名称" />
            </Form.Item>
            <Form.Item
              label="定义"
              name="definition"
              rules={[{ required: true, message: '请输入定义' }]}
            >
              <TextArea rows={4} placeholder="请输入定义" showCount />
            </Form.Item>
            <Form.Item label="案例" required>
              <Form.List name="cases">
                {(fields, { add, remove }) => (
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    {fields.map((field, index) => (
                      <Space key={field.key} align="start" style={{ display: 'flex' }}>
                        <Form.Item
                          {...field}
                          rules={[{ required: true, message: '请输入案例内容' }]}
                          style={{ flex: 1, marginBottom: 0 }}
                        >
                          <TextArea rows={4} placeholder={`案例 ${index + 1}`} />
                        </Form.Item>
                        <Button
                          danger
                          icon={<DeleteOutlined />}
                          disabled={fields.length === 1}
                          onClick={() => remove(field.name)}
                        >
                          删除
                        </Button>
                      </Space>
                    ))}
                    <Button icon={<PlusOutlined />} onClick={() => add('')}>
                      新增案例
                    </Button>
                  </Space>
                )}
              </Form.List>
            </Form.Item>
          </Form>
        )}
      </Drawer>
    </div>
  );
};
