import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LoginPage from './login';
import FlowList from './list';
import FlowConfig from './config';
import AdminUserPage from './flow/settings';
import MlflowPage from './model/registry';
import FlowEditor from './fullnode';
import FunctionManagerMain from './functions';
import SqlAutoLayout from './sql';
import PortfolioPage from './PortfolioPage';

const AppRoutes = () => (
  <Router basename="/ade">
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<FlowList />} />
      <Route path="/list" element={<FlowList />} />
      <Route path="/config" element={<FlowConfig />} />
      <Route path="/flow/settings/*" element={<AdminUserPage />} />
      <Route path="/model/registry/*" element={<MlflowPage />} />
      <Route path="/fullnode" element={<FlowEditor />} />
      <Route path="/functions" element={<FunctionManagerMain />} />
      <Route path="/sql" element={<SqlAutoLayout />} />
      <Route path="/portfolio" element={<PortfolioPage />} />
    </Routes>
  </Router>
);

export default AppRoutes;