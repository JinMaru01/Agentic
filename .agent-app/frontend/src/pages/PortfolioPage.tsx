/**
 * PortfolioPage - Main page for managing portfolios
 * Features: list view with pagination, create form, edit modal, delete confirmation, error handling
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  message,
  Card,
  Pagination,
  Divider,
  Space
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CloseOutlined
} from '@ant-design/icons';
import {
  getPortfolios,
  createPortfolio,
  updatePortfolio,
  deletePortfolio,
  getPortfolioById
} from '../../api/portfolio';
import { Portfolio } from '../../types';

// Define status options for the form
const statusOptions = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'draft', label: 'Draft' }
];

// Define pagination defaults
const DEFAULT_PAGE = 1;
const DEFAULT_LIMIT = 10;

const PortfolioPage: React.FC = () => {
  // State for the list view
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(DEFAULT_PAGE);
  const [limit, setLimit] = useState<number>(DEFAULT_LIMIT);
  const [search, setSearch] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);

  // State for modals
  const [createFormVisible, setCreateFormVisible] = useState<boolean>(false);
  const [editFormVisible, setEditFormVisible] = useState<boolean>(false);
  const [deleteModalVisible, setDeleteModalVisible] = useState<boolean>(false);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<number | null>(null);
  const [editingPortfolio, setEditingPortfolio] = useState<Portfolio | null>(null);

  // Form instance for create and edit
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  // Navigation
  const navigate = useNavigate();
  const { user } = useAuth();

  // Fetch portfolios on mount and when pagination/search changes
  const fetchPortfolios = useCallback(async () => {
    try {
      setLoading(true);
      const response = await getPortfolios(page, limit, search);
      if (response.data && Array.isArray(response.data)) {
        setPortfolios(response.data);
        setTotal(response.total || response.data.length);
      } else {
        setPortfolios([]);
        setTotal(0);
      }
    } catch (error) {
      console.error('Error fetching portfolios:', error);
      message.error('Failed to load portfolios');
      setPortfolios([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, limit, search]);

  // Load portfolios when component mounts or when dependencies change
  useEffect(() => {
    fetchPortfolios();
  }, [fetchPortfolios]);

  // Handle pagination change
  const handlePageChange = (page: number, limit: number) => {
    setPage(page);
    setLimit(limit);
  };

  // Handle search input change
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
  };

  // Handle create form submission
  const handleCreateSubmit = async () => {
    try {
      const values = await createForm.validateFields();
      await createPortfolio(values);
      message.success('Portfolio created successfully');
      setCreateFormVisible(false);
      createForm.resetFields();
      fetchPortfolios(); // Refresh the list
    } catch (error) {
      console.error('Error creating portfolio:', error);
      message.error('Failed to create portfolio');
    }
  };

  // Handle edit form submission
  const handleEditSubmit = async () => {
    if (!editingPortfolio) return;
    try {
      const values = await editForm.validateFields();
      await updatePortfolio(editingPortfolio.id, values);
      message.success('Portfolio updated successfully');
      setEditFormVisible(false);
      editForm.resetFields();
      fetchPortfolios(); // Refresh the list
    } catch (error) {
      console.error('Error updating portfolio:', error);
      message.error('Failed to update portfolio');
    }
  };

  // Handle edit button click
  const handleEditClick = async (id: number) => {
    try {
      const portfolio = await getPortfolioById(id);
      if (portfolio) {
        setEditingPortfolio(portfolio);
        editForm.setFieldsValue({
          name: portfolio.name,
          description: portfolio.description,
          status: portfolio.status
        });
        setEditFormVisible(true);
      }
    } catch (error) {
      console.error('Error fetching portfolio for edit:', error);
      message.error('Failed to load portfolio for editing');
    }
  };

  // Handle delete button click
  const handleDeleteClick = (id: number) => {
    setSelectedPortfolioId(id);
    setDeleteModalVisible(true);
  };

  // Handle delete confirmation
  const handleDeleteConfirm = async () => {
    if (selectedPortfolioId === null) return;
    try {
      await deletePortfolio(selectedPortfolioId);
      message.success('Portfolio deleted successfully');
      setDeleteModalVisible(false);
      setSelectedPortfolioId(null);
      fetchPortfolios(); // Refresh the list
    } catch (error) {
      console.error('Error deleting portfolio:', error);
      message.error('Failed to delete portfolio');
    }
  };

  // Handle delete cancel
  const handleDeleteCancel = () => {
    setDeleteModalVisible(false);
    setSelectedPortfolioId(null);
  };

  // Table columns definition
  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Portfolio) => (
        <a onClick={() => navigate(`/portfolio/${record.id}`)}>
          {text}
        </a>
      )
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      width: '30%'
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <span className={`status-${status}`}>{status.charAt(0).toUpperCase() + status.slice(1)}</span>
      )
    },
    {
      title: 'Created At',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleDateString()
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: Portfolio) => (
        <Space size="middle">
          <a onClick={() => handleEditClick(record.id)}>
            <EditOutlined /> Edit
          </a>
          <a onClick={() => handleDeleteClick(record.id)}>
            <DeleteOutlined /> Delete
          </a>
        </Space>
      )
    }
  ];

  return (
    <div className="p-6">
      <Card
        title="Portfolio Management"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateFormVisible(true)}
          >
            Create Portfolio
          </Button>
        }
        className="mb-6"
      >
        <div className="flex flex-col md:flex-row gap-4 mb-4">
          <Input
            placeholder="Search portfolios..."
            value={search}
            onChange={handleSearchChange}
            className="flex-1"
            allowClear
          />
          <Button
            type="default"
            onClick={() => setSearch('')}
            disabled={!search}
          >
            Clear
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={portfolios}
          rowKey="id"
          loading={loading}
          pagination={false}
          size="middle"
          className="mt-4"
        />

        <div className="flex justify-between items-center mt-4">
          <span>
            Showing {portfolios.length} of {total} portfolios
          </span>
          <Pagination
            current={page}
            total={total}
            pageSize={limit}
            onChange={handlePageChange}
            showSizeChanger
            onShowSizeChange={(current, size) => handlePageChange(current, size)}
            className="flex justify-end"
          />
        </div>
      </Card>

      {/* Create Portfolio Modal */}
      <Modal
        title="Create New Portfolio"
        open={createFormVisible}
        onOk={handleCreateSubmit}
        onCancel={() => {
          setCreateFormVisible(false);
          createForm.resetFields();
        }}
        width={600}
        destroyOnClose
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreateSubmit}>
          <Form.Item
            name="name"
            label="Portfolio Name"
            rules={[{ required: true, message: 'Please enter a portfolio name' }]}
          >
            <Input placeholder="Enter portfolio name" />
          </Form.Item>
          
          <Form.Item
            name="description"
            label="Description"
            rules={[{ required: true, message: 'Please enter a description' }]}
          >
            <Input.TextArea placeholder="Enter description" rows={4} />
          </Form.Item>
          
          <Form.Item
            name="status"
            label="Status"
            rules={[{ required: true, message: 'Please select a status' }]}
          >
            <Select placeholder="Select status">
              {statusOptions.map(option => (
                <Select.Option key={option.value} value={option.value}>
                  {option.label}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit Portfolio Modal */}
      <Modal
        title="Edit Portfolio"
        open={editFormVisible}
        onOk={handleEditSubmit}
        onCancel={() => {
          setEditFormVisible(false);
          editForm.resetFields();
        }}
        width={600}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" onFinish={handleEditSubmit}>
          <Form.Item
            name="name"
            label="Portfolio Name"
            rules={[{ required: true, message: 'Please enter a portfolio name' }]}
          >
            <Input placeholder="Enter portfolio name" />
          </Form.Item>
          
          <Form.Item
            name="description"
            label="Description"
            rules={[{ required: true, message: 'Please enter a description' }]}
          >
            <Input.TextArea placeholder="Enter description" rows={4} />
          </Form.Item>
          
          <Form.Item
            name="status"
            label="Status"
            rules={[{ required: true, message: 'Please select a status' }]}
          >
            <Select placeholder="Select status">
              {statusOptions.map(option => (
                <Select.Option key={option.value} value={option.value}>
                  {option.label}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        title="Confirm Delete"
        open={deleteModalVisible}
        onOk={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
        okText="Delete"
        cancelText="Cancel"
        okType="danger"
      >
        <p>Are you sure you want to delete this portfolio? This action cannot be undone.</p>
      </Modal>
    </div>
  );
};

export default PortfolioPage;