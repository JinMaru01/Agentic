import { axiosInstance } from './client';

// Define API endpoints
const PORTFOLIO_BASE = '/ade/api/portfolio';

// Portfolio API interface
export interface Portfolio {
  id: number;
  name: string;
  description: string;
  status: 'active' | 'inactive' | 'draft';
  created_at: string;
  updated_at: string;
}

// API functions
export const getPortfolios = async (page: number = 1, limit: number = 10, search: string = '') => {
  const response = await axiosInstance.get(`${PORTFOLIO_BASE}`, {
    params: { page, limit, search }
  });
  return response.data;
};

export const createPortfolio = async (portfolioData: Omit<Portfolio, 'id' | 'created_at' | 'updated_at'>) => {
  const response = await axiosInstance.post(`${PORTFOLIO_BASE}`, portfolioData);
  return response.data;
};

export const updatePortfolio = async (id: number, portfolioData: Partial<Portfolio>) => {
  const response = await axiosInstance.put(`${PORTFOLIO_BASE}/${id}`, portfolioData);
  return response.data;
};

export const deletePortfolio = async (id: number) => {
  const response = await axiosInstance.delete(`${PORTFOLIO_BASE}/${id}`);
  return response.data;
};

export const getPortfolioById = async (id: number) => {
  const response = await axiosInstance.get(`${PORTFOLIO_BASE}/${id}`);
  return response.data;
};

// Export all API functions
export default {
  getPortfolios,
  createPortfolio,
  updatePortfolio,
  deletePortfolio,
  getPortfolioById
};