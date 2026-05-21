export interface Portfolio {
  id: number;
  name: string;
  description: string;
  status: 'active' | 'inactive' | 'draft';
  created_at: string;
  updated_at: string;
  is_active: boolean;
}