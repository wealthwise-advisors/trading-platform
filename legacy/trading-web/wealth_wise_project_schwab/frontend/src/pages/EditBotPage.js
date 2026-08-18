import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { API_BASE_URL, STATIC_BASE_URL } from "../config";


export default function EditBotPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [customers, setCustomers] = useState([]);
  const [bot, setBot] = useState({
    bot_name: "",
    customer_id: "",
    symbol_ironbeam: "",
    symbol_schwab: "",
    lot_size: "",
    live_trading: false,
    strategy: "Strategy_One",
  });

  useEffect(() => {
    fetchBot();
    fetchCustomers();
  }, [id]); // Runs when `id` changes

  const fetchBot = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/bots/${id}`);
      setBot(response.data);
    } catch (error) {
      console.error("Error fetching bot details:", error);
    }
  };

  const fetchCustomers = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/customers`);
      setCustomers(response.data);
    } catch (error) {
      console.error("Error fetching customers:", error);
    }
  };

  const updateBot = async () => {
    try {
      await axios.put(`${API_BASE_URL}/bots/${id}`, bot);
      navigate("/bots");
    } catch (error) {
      console.error("Error updating bot:", error);
    }
  };

  return (
    <div className="bg-white shadow-md rounded p-6">
      <h2 className="text-xl font-semibold mb-4">Edit Bot</h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <input
          type="text"
          placeholder="Bot Name"
          value={bot.bot_name}
          onChange={(e) => setBot({ ...bot, bot_name: e.target.value })}
          className="w-full border p-2 rounded"
        />
        <select
          value={bot.customer_id}
          onChange={(e) => setBot({ ...bot, customer_id: e.target.value })}
          className="w-full border p-2 rounded"
        >
          <option value="">Select Customer</option>
          {customers.map((customer) => (
            <option key={customer.customer_id} value={customer.customer_id}>
              {customer.customer_id} - {customer.customer_name}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Symbol (Ironbeam)"
          value={bot.symbol_ironbeam}
          onChange={(e) => setBot({ ...bot, symbol_ironbeam: e.target.value })}
          className="w-full border p-2 rounded"
        />
        <input
          type="text"
          placeholder="Symbol (Schwab)"
          value={bot.symbol_schwab}
          onChange={(e) => setBot({ ...bot, symbol_schwab: e.target.value })}
          className="w-full border p-2 rounded"
        />
        <input
          type="number"
          placeholder="Lot Size"
          value={bot.lot_size}
          onChange={(e) => setBot({ ...bot, lot_size: e.target.value })}
          className="w-full border p-2 rounded"
        />
        <input
          type="number"
          placeholder="Stop Loss Adjust"
          value={bot.stop_loss_adjust}
          onChange={(e) => setBot({ ...bot, stop_loss_adjust: e.target.value })}
          className="w-full border p-2 rounded"
        />
        <select
          value={bot.strategy}
          onChange={(e) => setBot({ ...bot, strategy: e.target.value })}
          className="w-full border p-2 rounded"
        >
            <option value="Strategy_One">Strategy One</option>
            <option value="Strategy_Two">Strategy Two</option>
            <option value="Strategy_Three">Strategy Three</option>

        </select>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={bot.live_trading}
            onChange={(e) => setBot({ ...bot, live_trading: e.target.checked })}
          />
          Live Trading
        </label>
      </div>
      <button
        onClick={updateBot}
        className="bg-green-500 text-white px-4 py-2 mt-4 rounded hover:bg-green-600"
      >
        Update Bot
      </button>
    </div>
  );
}
