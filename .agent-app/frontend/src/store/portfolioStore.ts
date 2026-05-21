import { create } from 'zustand';
import { Portfolio } from '../api/portfolio';
import { getPortfolios } from '../api/portfolio';

// Define the store state interface
interface PortfolioState {
  portfolios: Portfolio[];
  total: number;
  page: number;
  limit: number;
  search: string;
  loading: boolean;
  error: string | null;
  selectedPortfolio: Portfolio | null;

  // Actions
  setPortfolios: (portfolios: Portfolio[], total: number) => void;
  setPage: (page: number) => void;
  setLimit: (limit: number) => void;
  setSearch: (search: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setSelectedPortfolio: (portfolio: Portfolio | null) => void;
  reset: () => void;
}

// Create the store
export const usePortfolioStore = create<PortfolioState>((set, get) => ({
  portfolios: [],
  total: 0,
  page: 1,
  limit: 10,
  search: '',
  loading: false,
  error: null,
  selectedPortfolio: null,

  setPortfolios: (portfolios, total) => set({ portfolios, total }),
  setPage: (page) => set({ page }),
  setLimit: (limit) => set({ limit }),
  setSearch: (search) => set({ search, page: 1 }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  setSelectedPortfolio: (portfolio) => set({ selectedPortfolio: portfolio }),
  reset: () => set({
    portfolios: [],
    total: 0,
    page: 1,
    limit: 10,
    search: '',
    loading: false,
    error: null,
    selectedPortfolio: null
  })
}));

// Helper function to fetch portfolios
export const fetchPortfolios = async () => {
  const store = usePortfolioStore.getState();
  const { page, limit, search } = store;
  
  try {
    usePortfolioStore.getState().setLoading(true);
    const response = await getPortfolios(page, limit, search);
    usePortfolioStore.getState().setPortfolios(response.data, response.total);
  } catch (error) {
    usePortfolioStore.getState().setError('Failed to fetch portfolios');
  } finally {
    usePortfolioStore.getState().setLoading(false);
  }
};