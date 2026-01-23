import React, { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  Modal,
  Row,
  Space,
  Spin,
  Tabs,
  Typography,
  Upload,
  message,
  Table,
} from 'antd';
import type { UploadFile } from 'antd/es/upload/interface';
import { PlusOutlined, UploadOutlined, EditOutlined, DeleteOutlined, ReloadOutlined, FolderOutlined, FolderOpenOutlined, FileTextOutlined, TagOutlined } from '@ant-design/icons';
import { Tree } from 'antd';
import { apiClient } from '@/api/client';
import { useAuthStore } from '@/store/auth';

const { Text, Title } = Typography;
const { TextArea } = Input;

type ScopeCode = 'water' | 'bus' | 'bike';

interface TreeNode {
  id: number;
  name: string;
  level: number;
  parentId?: number | null;
  children: TreeNode[];
}

interface TreeResponse {
  items: TreeNode[];
}

interface PathSegment {
  id: number;
  name: string;
  level: number;
}

interface NodeDetailResponse {
  id: number;
  scopeCode: ScopeCode;
  level: number;
  name: string;
  parentId?: number | null;
  definition?: string | null;
  path: PathSegment[];
}

interface CaseItem {
  id: number;
  nodeId: number;
  content: string;
}

interface CaseListResponse {
  items: CaseItem[];
}

interface ImportError {
  row: number;
  column: string;
  message: string;
  expected?: string | null;
  actual?: string | null;
}

interface ImportSummary {
  categories: number;
  cases: number;
}

interface ImportValidateResponse {
  ok: boolean;
  summary?: ImportSummary | null;
  errors: ImportError[];
}

function toAntTreeData(nodes: TreeNode[]): any[] {
  return nodes.map((n) => {
    const getLevelConfig = (level: number) => {
      switch (level) {
        case 1:
          return { icon: <FolderOutlined />, badge: 'L1', color: '#1890ff' };
        case 2:
          return { icon: <FolderOpenOutlined />, badge: 'L2', color: '#faad14' };
        case 3:
          return { icon: <FileTextOutlined />, badge: 'L3', color: '#52c41a' };
        default:
          return { icon: <TagOutlined />, badge: 'L?', color: '#8c8c8c' };
      }
    };

    const config = getLevelConfig(n.level);

    return {
      key: String(n.id),
      title: n.name,
      level: n.level,
      icon: config.icon,
      levelBadge: config.badge,
      levelColor: config.color,
      children: toAntTreeData(n.children || []),
    };
  });
}

// 自定义节点渲染
function renderTreeNode(nodeData: any) {
  return (
    <div className="custom-tree-node" data-level={nodeData.level}>
      <span
        className="level-badge"
        style={{
          backgroundColor: nodeData.levelColor,
          color: '#fff',
          padding: '2px 6px',
          borderRadius: '3px',
          fontSize: '11px',
          fontWeight: 600,
          marginRight: '8px',
          display: 'inline-block',
          minWidth: '28px',
          textAlign: 'center'
        }}
      >
        {nodeData.levelBadge}
      </span>
      <span className="node-title" style={{ fontSize: '14px' }}>
        {nodeData.title}
      </span>
    </div>
  );
}

function filterTree(nodes: TreeNode[], keyword: string): TreeNode[] {
  const k = keyword.trim();
  if (!k) return nodes;
  const walk = (items: TreeNode[]): TreeNode[] =>
    items
      .map((n) => {
        const children = walk(n.children || []);
        const hit = n.name.includes(k);
        if (hit || children.length > 0) {
          return { ...n, children };
        }
        return null;
      })
      .filter(Boolean) as TreeNode[];
  return walk(nodes);
}

export const TaxonomyKBPage: React.FC = () => {
  const user = useAuthStore((s) => s.user);
  const isBusUser = user?.scenarioId === 2;

  const [scope, setScope] = useState<ScopeCode>(isBusUser ? 'bus' : 'water');
  const [treeKeyword, setTreeKeyword] = useState('');
  const [treeLoading, setTreeLoading] = useState(false);
  const [tree, setTree] = useState<TreeNode[]>([]);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState<NodeDetailResponse | null>(null);

  const [caseKeyword, setCaseKeyword] = useState('');
  const [casesLoading, setCasesLoading] = useState(false);
  const [cases, setCases] = useState<CaseItem[]>([]);

  const [nodeModalOpen, setNodeModalOpen] = useState(false);
  const [nodeModalMode, setNodeModalMode] = useState<'create' | 'edit'>('create');
  const [nodeCreateLevel, setNodeCreateLevel] = useState<1 | 2 | 3>(1);
  const [nodeParentId, setNodeParentId] = useState<number | null>(null);
  const [nodeForm] = Form.useForm();

  const [caseModalOpen, setCaseModalOpen] = useState(false);
  const [editingCaseId, setEditingCaseId] = useState<number | null>(null);
  const [caseForm] = Form.useForm();

  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importFile, setImportFile] = useState<UploadFile | null>(null);
  const [importValidating, setImportValidating] = useState(false);
  const [importExecuting, setImportExecuting] = useState(false);
  const [importResult, setImportResult] = useState<ImportValidateResponse | null>(null);

  const visibleTree = useMemo(() => filterTree(tree, treeKeyword), [tree, treeKeyword]);

  const loadTree = async (nextScope: ScopeCode) => {
    setTreeLoading(true);
    try {
      const { data } = await apiClient.get<TreeResponse>('/api/v1.12/kb-taxonomy/tree', {
        params: { scope: nextScope },
      });
      setTree(data.items || []);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '加载分类树失败');
      setTree([]);
    } finally {
      setTreeLoading(false);
    }
  };

  const loadDetail = async (nodeId: number) => {
    setDetailLoading(true);
    try {
      const { data } = await apiClient.get<NodeDetailResponse>(`/api/v1.12/kb-taxonomy/nodes/${nodeId}`, {
        params: { scope },
      });
      setDetail(data);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '加载详情失败');
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const loadCases = async (nodeId: number, keyword?: string) => {
    setCasesLoading(true);
    try {
      const { data } = await apiClient.get<CaseListResponse>(`/api/v1.12/kb-taxonomy/nodes/${nodeId}/cases`, {
        params: { scope, keyword: keyword?.trim() || undefined },
      });
      setCases(data.items || []);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '加载案例失败');
      setCases([]);
    } finally {
      setCasesLoading(false);
    }
  };

  useEffect(() => {
    void loadTree(scope);
    setSelectedId(null);
    setDetail(null);
    setCases([]);
    setCaseKeyword('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope]);

  useEffect(() => {
    if (!selectedId) return;
    void loadDetail(selectedId);
    void loadCases(selectedId, caseKeyword);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  const refresh = async () => {
    await loadTree(scope);
    if (selectedId) {
      await loadDetail(selectedId);
      await loadCases(selectedId, caseKeyword);
    }
  };

  const openCreateNodeModal = (level: 1 | 2 | 3, parentId: number | null) => {
    setNodeModalMode('create');
    setNodeCreateLevel(level);
    setNodeParentId(parentId);
    nodeForm.resetFields();
    setNodeModalOpen(true);
  };

  const openEditNodeModal = () => {
    if (!detail) return;
    setNodeModalMode('edit');
    setNodeCreateLevel(detail.level as 1 | 2 | 3);
    setNodeParentId(detail.parentId ?? null);
    nodeForm.setFieldsValue({
      name: detail.name,
      definition: detail.definition || '',
    });
    setNodeModalOpen(true);
  };

  const saveNode = async () => {
    try {
      const values = await nodeForm.validateFields();
      if (nodeModalMode === 'create') {
        await apiClient.post('/api/v1.12/kb-taxonomy/nodes', {
          scope,
          parentId: nodeParentId ?? undefined,
          level: nodeCreateLevel,
          name: values.name,
          definition: nodeCreateLevel === 3 ? values.definition : undefined,
        });
        message.success('创建成功');
      } else {
        if (!detail) return;
        await apiClient.put(`/api/v1.12/kb-taxonomy/nodes/${detail.id}`, {
          scope,
          name: values.name,
          definition: detail.level === 3 ? values.definition : undefined,
        });
        message.success('更新成功');
      }
      setNodeModalOpen(false);
      await refresh();
    } catch (error: any) {
      if (error?.response?.data?.detail) {
        message.error(error.response.data.detail);
      }
    }
  };

  const deleteSelectedNode = async () => {
    if (!detail) return;
    Modal.confirm({
      title: '确认删除',
      content: detail.level === 3 ? '删除三级分类将同时删除其下全部案例，是否继续？' : '确认删除该分类吗？',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await apiClient.delete(`/api/v1.12/kb-taxonomy/nodes/${detail.id}`, { params: { scope } });
          message.success('删除成功');
          setSelectedId(null);
          setDetail(null);
          setCases([]);
          await loadTree(scope);
        } catch (error: any) {
          message.error(error?.response?.data?.detail || '删除失败');
        }
      },
    });
  };

  const openCreateCaseModal = () => {
    if (!detail || detail.level !== 3) return;
    setEditingCaseId(null);
    caseForm.resetFields();
    setCaseModalOpen(true);
  };

  const openEditCaseModal = (item: CaseItem) => {
    setEditingCaseId(item.id);
    caseForm.setFieldsValue({ content: item.content });
    setCaseModalOpen(true);
  };

  const saveCase = async () => {
    if (!detail || detail.level !== 3) return;
    try {
      const values = await caseForm.validateFields();
      if (editingCaseId) {
        await apiClient.put(`/api/v1.12/kb-taxonomy/cases/${editingCaseId}`, { scope, content: values.content });
        message.success('更新成功');
      } else {
        await apiClient.post('/api/v1.12/kb-taxonomy/cases', { scope, nodeId: detail.id, content: values.content });
        message.success('新增成功');
      }
      setCaseModalOpen(false);
      await loadCases(detail.id, caseKeyword);
    } catch (error: any) {
      if (error?.response?.data?.detail) {
        message.error(error.response.data.detail);
      }
    }
  };

  const deleteCase = (item: CaseItem) => {
    Modal.confirm({
      title: '确认删除案例',
      content: '删除后不可恢复，是否继续？',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await apiClient.delete(`/api/v1.12/kb-taxonomy/cases/${item.id}`, { params: { scope } });
          message.success('删除成功');
          if (detail) await loadCases(detail.id, caseKeyword);
        } catch (error: any) {
          message.error(error?.response?.data?.detail || '删除失败');
        }
      },
    });
  };

  const openImportModal = () => {
    setImportFile(null);
    setImportResult(null);
    setImportModalOpen(true);
  };

  const validateImport = async () => {
    if (!importFile?.originFileObj) {
      message.warning('请先选择CSV文件');
      return;
    }
    setImportValidating(true);
    try {
      const formData = new FormData();
      formData.append('file', importFile.originFileObj);
      const { data } = await apiClient.post<ImportValidateResponse>('/api/v1.12/kb-taxonomy/import/validate', formData, {
        params: { scope },
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60_000,
      });
      setImportResult(data);
      if (data.ok) {
        message.success(`校验通过：将导入${data.summary?.categories ?? 0}个三级分类、${data.summary?.cases ?? 0}条案例`);
      } else {
        message.error('校验失败，请修正CSV后重试');
      }
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '校验失败');
    } finally {
      setImportValidating(false);
    }
  };

  const executeImport = async () => {
    if (!importFile?.originFileObj) {
      message.warning('请先选择CSV文件');
      return;
    }
    Modal.confirm({
      title: '确认覆盖导入',
      content: '将清空并覆盖当前范围全部分类与案例数据，是否继续？',
      okText: '确认覆盖并导入',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setImportExecuting(true);
        try {
          const formData = new FormData();
          formData.append('file', importFile.originFileObj);
          const { data } = await apiClient.post<ImportValidateResponse>('/api/v1.12/kb-taxonomy/import/execute', formData, {
            params: { scope },
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 5 * 60_000,
          });
          setImportResult(data);
          if (data.ok) {
            message.success('导入成功');
            setImportModalOpen(false);
            await refresh();
          } else {
            message.error('导入失败，请修正CSV后重试');
          }
        } catch (error: any) {
          message.error(error?.response?.data?.detail || '导入失败');
        } finally {
          setImportExecuting(false);
        }
      },
    });
  };

  const tabItems = [
    { key: 'bus', label: '公交' },
    { key: 'bike', label: '自行车' },
  ];

  const scopeLabel = scope === 'water' ? '水务' : scope === 'bus' ? '公交' : '自行车';

  return (
    <div>
      <Card size="small" style={{ marginBottom: 12 }}>
        <Row align="middle" justify="space-between" gutter={16}>
          <Col>
            <Space direction="vertical" size={0}>
              <Title level={4} style={{ margin: 0 }}>
                分类知识库
              </Title>
              <Text type="secondary">当前范围：{scopeLabel}</Text>
            </Space>
          </Col>
          <Col>
            <Space>
              <Button icon={<UploadOutlined />} onClick={openImportModal}>
                导入CSV（覆盖当前范围）
              </Button>
              <Button icon={<ReloadOutlined />} onClick={() => void refresh()} loading={treeLoading || detailLoading}>
                刷新
              </Button>
            </Space>
          </Col>
        </Row>
        {isBusUser ? (
          <Tabs
            style={{ marginTop: 12 }}
            activeKey={scope}
            items={tabItems}
            onChange={(key) => setScope(key as ScopeCode)}
          />
        ) : null}
      </Card>

      <Row gutter={12}>
        <Col span={8}>
          <Card size="small" title="三级分类树" extra={<Button onClick={() => openCreateNodeModal(1, null)} icon={<PlusOutlined />}>新增一级</Button>}>
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Input
                placeholder="搜索分类名称..."
                value={treeKeyword}
                onChange={(e) => setTreeKeyword(e.target.value)}
                allowClear
              />
              <div
                style={{
                  height: 'calc(100vh - 320px)',
                  minHeight: '500px',
                  maxHeight: '700px',
                  overflowY: 'auto',
                  overflowX: 'hidden',
                  paddingRight: '8px'
                }}
                className="tree-scroll-container"
              >
                {treeLoading ? (
                  <div style={{ padding: 24, textAlign: 'center' }}>
                    <Spin />
                  </div>
                ) : visibleTree.length === 0 ? (
                  <Empty description="暂无数据，请先导入CSV或新增分类" />
                ) : (
                  <Tree
                    showLine={{ showLeafIcon: false }}
                    showIcon
                    treeData={toAntTreeData(visibleTree)}
                    titleRender={renderTreeNode}
                    selectedKeys={selectedId ? [String(selectedId)] : []}
                    onSelect={(keys) => {
                      const id = Number(keys?.[0]);
                      if (!Number.isFinite(id)) return;
                      setSelectedId(id);
                    }}
                    defaultExpandAll
                    style={{
                      fontSize: '14px',
                      lineHeight: '32px',
                    }}
                    className="custom-taxonomy-tree"
                  />
                )}
              </div>
            </Space>
          </Card>
        </Col>

        <Col span={16}>
          <Card
            size="small"
            title="三级详情"
            extra={
              <Space>
                <Button
                  icon={<PlusOutlined />}
                  disabled={!detail || detail.level === 3}
                  onClick={() => {
                    if (!detail) return;
                    if (detail.level === 1) openCreateNodeModal(2, detail.id);
                    else if (detail.level === 2) openCreateNodeModal(3, detail.id);
                  }}
                >
                  新增子节点
                </Button>
                <Button icon={<EditOutlined />} disabled={!detail} onClick={openEditNodeModal}>
                  编辑
                </Button>
                <Button danger icon={<DeleteOutlined />} disabled={!detail} onClick={() => void deleteSelectedNode()}>
                  删除
                </Button>
              </Space>
            }
          >
            {detailLoading ? (
              <div style={{ padding: 24, textAlign: 'center' }}>
                <Spin />
              </div>
            ) : !detail ? (
              <Empty description="请选择左侧一个分类节点" />
            ) : (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <div>
                  <Text type="secondary">路径：</Text>
                  <Text>
                    {detail.path.map((p) => p.name).join(' / ') || '-'}
                  </Text>
                </div>
                <div>
                  <Text type="secondary">定义：</Text>
                  {detail.level === 3 ? (
                    <div style={{ marginTop: 8, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {detail.definition || <Text type="secondary">—</Text>}
                    </div>
                  ) : (
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary">请选择三级节点查看定义与案例</Text>
                    </div>
                  )}
                </div>

                <Card
                  size="small"
                  title="案例（默认全部展开）"
                  extra={
                    <Space>
                      <Input
                        placeholder="在本三级内搜索案例关键词..."
                        value={caseKeyword}
                        onChange={(e) => setCaseKeyword(e.target.value)}
                        onPressEnter={() => detail.level === 3 && void loadCases(detail.id, caseKeyword)}
                        allowClear
                        style={{ width: 280 }}
                        disabled={detail.level !== 3}
                      />
                      <Button
                        type="primary"
                        onClick={() => detail.level === 3 && void loadCases(detail.id, caseKeyword)}
                        disabled={detail.level !== 3}
                        loading={casesLoading}
                      >
                        搜索
                      </Button>
                      <Button icon={<PlusOutlined />} onClick={openCreateCaseModal} disabled={detail.level !== 3}>
                        新增案例
                      </Button>
                    </Space>
                  }
                >
                  {detail.level !== 3 ? (
                    <Empty description="请选择三级分类查看案例" />
                  ) : casesLoading ? (
                    <div style={{ padding: 24, textAlign: 'center' }}>
                      <Spin />
                    </div>
                  ) : cases.length === 0 ? (
                    <Empty description="暂无案例" />
                  ) : (
                    <Space direction="vertical" style={{ width: '100%' }} size="middle">
                      {cases.map((c, idx) => (
                        <Card
                          key={c.id}
                          size="small"
                          title={`案例#${idx + 1}`}
                          extra={
                            <Space>
                              <Button size="small" icon={<EditOutlined />} onClick={() => openEditCaseModal(c)}>
                                编辑
                              </Button>
                              <Button size="small" danger icon={<DeleteOutlined />} onClick={() => deleteCase(c)}>
                                删除
                              </Button>
                            </Space>
                          }
                        >
                          <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{c.content}</div>
                        </Card>
                      ))}
                    </Space>
                  )}
                </Card>
              </Space>
            )}
          </Card>
        </Col>
      </Row>

      <Modal
        title={nodeModalMode === 'create' ? '新增分类' : '编辑分类'}
        open={nodeModalOpen}
        onCancel={() => setNodeModalOpen(false)}
        onOk={() => void saveNode()}
        okText="保存"
        cancelText="取消"
      >
        <Form form={nodeForm} layout="vertical">
          <Form.Item
            label="名称"
            name="name"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="请输入分类名称" />
          </Form.Item>
          {nodeModalMode === 'create' ? (
            <Text type="secondary">
              将创建 {nodeCreateLevel === 1 ? '一级' : nodeCreateLevel === 2 ? '二级' : '三级'} 节点
            </Text>
          ) : null}
          {(nodeModalMode === 'create' ? nodeCreateLevel === 3 : detail?.level === 3) ? (
            <Form.Item
              label="定义"
              name="definition"
              rules={[{ required: true, message: '请输入定义' }]}
            >
              <TextArea rows={4} placeholder="请输入三级定义（支持多行）" />
            </Form.Item>
          ) : null}
        </Form>
      </Modal>

      <Modal
        title={editingCaseId ? '编辑案例' : '新增案例'}
        open={caseModalOpen}
        onCancel={() => setCaseModalOpen(false)}
        onOk={() => void saveCase()}
        okText="保存"
        cancelText="取消"
        width={720}
      >
        <Form form={caseForm} layout="vertical">
          <Form.Item
            label="对话全文"
            name="content"
            rules={[{ required: true, message: '请输入对话全文' }]}
          >
            <TextArea rows={10} placeholder="请输入多行对话全文" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`导入CSV（覆盖当前范围：${scopeLabel}）`}
        open={importModalOpen}
        onCancel={() => setImportModalOpen(false)}
        footer={
          <Space>
            <Button onClick={() => setImportModalOpen(false)}>取消</Button>
            <Button onClick={() => void validateImport()} loading={importValidating} disabled={!importFile}>
              开始校验
            </Button>
            <Button
              type="primary"
              danger
              onClick={() => void executeImport()}
              loading={importExecuting}
              disabled={!importFile}
            >
              确认覆盖并导入
            </Button>
          </Space>
        }
        width={900}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Upload
            accept=".csv,.xlsx"
            maxCount={1}
            beforeUpload={() => false}
            fileList={importFile ? [importFile] : []}
            onChange={(info) => {
              const f = info.fileList?.[0] || null;
              setImportFile(f);
              setImportResult(null);
            }}
          >
            <Button icon={<UploadOutlined />}>选择CSV/XLSX文件</Button>
          </Upload>

          <Text type="secondary">提示：校验通过后将清空并覆盖当前范围全部数据</Text>

          {importResult?.ok ? (
            <Card size="small">
              <Text>
                将导入 <b>{importResult.summary?.categories ?? 0}</b> 个三级分类、<b>{importResult.summary?.cases ?? 0}</b> 条案例
              </Text>
            </Card>
          ) : null}

          {importResult && !importResult.ok ? (
            <Table
              size="small"
              rowKey={(r) => `${r.row}-${r.column}-${r.message}`}
              dataSource={importResult.errors || []}
              pagination={{ pageSize: 8 }}
              columns={[
                { title: '行号', dataIndex: 'row', width: 80 },
                { title: '列名', dataIndex: 'column', width: 120 },
                { title: '原因', dataIndex: 'message' },
                { title: '期望', dataIndex: 'expected', width: 180 },
                { title: '实际', dataIndex: 'actual', width: 180 },
              ]}
            />
          ) : null}
        </Space>
      </Modal>
    </div>
  );
};
