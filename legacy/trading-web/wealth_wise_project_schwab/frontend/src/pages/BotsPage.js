import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { FaTrash } from "react-icons/fa"; // Import delete icon
import { API_BASE_URL, STATIC_BASE_URL } from "../config";


export default function BotsPage() {
  const [bots, setBots] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [newBot, setNewBot] = useState({
    bot_name: "",
    customer_id: "",
    symbol_ironbeam: "",
    symbol_schwab: "",
    lot_size: "",
    live_trading: false,
    strategy: "Strategy_One",
  });

  useEffect(() => {
    fetchBots();
    fetchCustomers();
  }, []);

  const fetchBots = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/bots`);
      setBots(response.data);
    } catch (error) {
      console.error("Error fetching bots:", error);
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

  const addBot = async () => {
    if (!newBot.bot_name || !newBot.customer_id || !newBot.symbol_ironbeam || !newBot.symbol_schwab || !newBot.lot_size) {
      alert("Please fill in all required fields.");
      return;
    }
    try {
      await axios.post(`${API_BASE_URL}/bots`, newBot);
      setNewBot({
        bot_name: "",
        customer_id: "",
        symbol_ironbeam: "",
        symbol_schwab: "",
        lot_size: "",
        live_trading: false,
        strategy: "Strategy_One",
      });
      fetchBots();
    } catch (error) {
      console.error("Error adding bot:", error);
    }
  };

  const deleteBot = async (botId) => {
    if (!window.confirm("Are you sure you want to delete this bot?")) return;

    try {
      await axios.delete(`${API_BASE_URL}/bots/${botId}`);
      setBots(bots.filter((bot) => bot.bot_id !== botId)); // Update UI
    } catch (error) {
      console.error("Error deleting bot:", error);
    }
  };

  return (
    <div className="bg-white shadow-md rounded p-6">
      <div className="mb-6">
        <h3 className="text-lg font-semibold mb-2">Add New Bot</h3>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <input
            type="text"
            placeholder="Bot Name"
            value={newBot.bot_name}
            onChange={(e) => setNewBot({ ...newBot, bot_name: e.target.value })}
            className="w-full border p-2 rounded"
          />
          <select
            value={newBot.customer_id}
            onChange={(e) => setNewBot({ ...newBot, customer_id: e.target.value })}
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
            value={newBot.symbol_ironbeam}
            onChange={(e) => setNewBot({ ...newBot, symbol_ironbeam: e.target.value })}
            className="w-full border p-2 rounded"
          />
          <input
            type="text"
            placeholder="Symbol (Schwab)"
            value={newBot.symbol_schwab}
            onChange={(e) => setNewBot({ ...newBot, symbol_schwab: e.target.value })}
            className="w-full border p-2 rounded"
          />
          <input
            type="number"
            placeholder="Lot Size"
            value={newBot.lot_size}
            onChange={(e) => setNewBot({ ...newBot, lot_size: e.target.value })}
            className="w-full border p-2 rounded"
          />
        <input
          type="number"
          placeholder="Stop Loss Adjust"
          value={newBot.stop_loss_adjust}
          onChange={(e) => setNewBot({ ...newBot, stop_loss_adjust: e.target.value })}
          className="w-full border p-2 rounded"
        />
          <select
            value={newBot.strategy}
            onChange={(e) => setNewBot({ ...newBot, strategy: e.target.value })}
            className="w-full border p-2 rounded"
          >
            <option value="Strategy_One">Strategy One</option>
            <option value="Strategy_Two">Strategy Two</option>
            <option value="Strategy_Three">Strategy Three</option>

          </select>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={newBot.live_trading}
              onChange={(e) => setNewBot({ ...newBot, live_trading: e.target.checked })}
            />
            Live Trading
          </label>
        </div>
        <button
          onClick={addBot}
          className="bg-green-500 text-white px-4 py-2 mt-4 rounded hover:bg-green-600"
        >
          Add Bot
        </button>
      </div>

      {/* Bot Table */}
      <table className="w-full border-collapse border border-gray-300">
        <thead>
          <tr className="bg-gray-200">
            <th className="border border-gray-300 p-2">ID</th>
            <th className="border border-gray-300 p-2">Bot Name</th>
            <th className="border border-gray-300 p-2">Customer</th>
            <th className="border border-gray-300 p-2">Symbol (Ironbeam)</th>
            <th className="border border-gray-300 p-2">Symbol (Schwab)</th>
            <th className="border border-gray-300 p-2">Lot Size</th>
            <th className="border border-gray-300 p-2">Stop Loss Adjust</th>
            <th className="border border-gray-300 p-2">Strategy</th>
            <th className="border border-gray-300 p-2">Live Trading</th>
            <th className="border border-gray-300 p-2">Current Trade</th>
            <th className="border border-gray-300 p-2">Status</th> {/* STOPPED or RUNNING */}
            <th className="border border-gray-300 p-2">Actions</th> {/* Delete Column */}
          </tr>
        </thead>
        <tbody>
          {bots.map((bot) => (
            <tr key={bot.bot_id} className="text-center">
              <td className="border border-gray-300 p-2">
                <Link to={`/bots/edit/${bot.bot_id}`} className="text-blue-600 underline">
                  {bot.bot_id}
                </Link>
              </td>
              <td className="border border-gray-300 p-2">{bot.bot_name}</td>
              <td className="border border-gray-300 p-2">
                {customers.find((customer) => customer.customer_id === bot.customer_id)?.customer_name || "N/A"}
              </td>
              <td className="border border-gray-300 p-2">{bot.symbol_ironbeam}</td>
              <td className="border border-gray-300 p-2">{bot.symbol_schwab}</td>
              <td className="border border-gray-300 p-2">{bot.lot_size}</td>
              <td className="border border-gray-300 p-2">{bot.stop_loss_adjust}</td>
              <td className="border border-gray-300 p-2">{bot.strategy}</td>
              <td className="border border-gray-300 p-2">{bot.live_trading ? "Yes" : "No"}</td>
              <td className="border border-gray-300 p-2">{bot.current_trade_status}</td>
              <td className="border border-gray-300 p-2 font-bold">{bot.status}</td>
              <td className="border border-gray-300 p-2">
                <button onClick={() => deleteBot(bot.bot_id)} className="text-red-500 hover:text-red-700">
                  <FaTrash />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
