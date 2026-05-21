/**
 * Portfolio model types based on backend app/models/portfolio.py
 */

export interface PortfolioCreate {
  name: string;
  description?: string | null;
  status?: string;
  owner_id: number;
}

export interface PortfolioUpdate {
  name: string;
  description?: string | null;
  status?: string | null;
  owner_id: number;
}

export interface PortfolioResponse {
  id: number;
  name: string;
  description?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}