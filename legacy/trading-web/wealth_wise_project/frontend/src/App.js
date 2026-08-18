import React from "react";
import { BrowserRouter as Router, Route, Routes, Link } from "react-router-dom";
import BotsPage from "./pages/BotsPage";
import ManageBotsPage from "./pages/ManageBotsPage";
import TradesPage from "./pages/TradesPage";
import CustomersPage from "./pages/CustomersPage";
import EditCustomerPage from "./pages/EditCustomerPage";
import EditBotPage from "./pages/EditBotPage";
import BacktestingPage from "./pages/BacktestingPage.js";

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-green-100 p-8">
        <h1 className="text-3xl font-bold text-center text-green-700 mb-6">Trading Bot</h1>
        <nav className="flex justify-center gap-4 mb-6">
          <Link to="/customers">Customers</Link>
          <Link to="/bots">Bots</Link>
          <Link to="/managebots">Manage Bots</Link>
          <Link to="/backtest">Back Testing</Link>
          <Link to="/trades">Trades</Link>
        </nav>
        <Routes>
          <Route path="/customers" element={<CustomersPage />} />
          <Route path="/customers/edit/:id" element={<EditCustomerPage />} />
          <Route path="/bots" element={<BotsPage />} />
          <Route path="/managebots" element={<ManageBotsPage />} />
          <Route path="/backtest" element={<BacktestingPage />} />
          <Route path="/bots/edit/:id" element={<EditBotPage />} />
          <Route path="/trades" element={<TradesPage />} />
        </Routes>
      </div>
    </Router>
  );
}
