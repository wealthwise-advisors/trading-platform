import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { API_BASE_URL } from "../config";

export default function ManageBotsPage() {
  const [bots, setBots] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [selectedBots, setSelectedBots] = useState(new Set());
  const [bulkLotSize, setBulkLotSize] = useState(0); // Lot size for BULK BUY/SELL
  const [startInProgress, setStartInProgress] = useState(false);

    useEffect(() => {
        fetchBots();
        fetchCustomers();

        // Regular update every 5 seconds
        const interval = setInterval(() => {
            fetchBots();
        }, 5000);

        // Function to check time and trigger fetchBots() at every XX:XX:03
        const checkAndFetchOn03 = () => {
            const now = new Date();
            if (now.getSeconds() === 3) {
                fetchBots();
            }
        };

        // Check every second if the time is XX:XX:03
        const secondCheckInterval = setInterval(checkAndFetchOn03, 1000);

        return () => {
            clearInterval(interval);         // Clear 5-second interval
            clearInterval(secondCheckInterval); // Clear per-second check
        };
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

  const toggleBotSelection = (botId) => {
    setSelectedBots((prevSelected) => {
      const newSelection = new Set(prevSelected);
      if (newSelection.has(botId)) {
        newSelection.delete(botId);
      } else {
        newSelection.add(botId);
      }
      return newSelection;
    });
  };

  const handleAction = async (action) => {
    if (selectedBots.size === 0) {
      alert("Please select at least one bot to perform this action.");
      return;
    }

    if (action === "START") {
      setStartInProgress(true);
    }
    const botIds = Array.from(selectedBots);

    try {
      await axios.post(`${API_BASE_URL}/bots/action`, {
        action,
        bot_ids: botIds,
      });

      alert(`${action} action executed successfully.`);
      fetchBots(); // Refresh bots after action
    } catch (error) {
      console.error(`Error executing ${action}:`, error);
    } finally {
         if (action === "START") {
                setStartInProgress(false);
         }
    }
  };

  const handleBulkTrade = async (action) => {
    if (bulkLotSize <= 0) {
      alert("Lot size must be greater than 0.");
      return;
    }

    const botIds = selectedBots.size > 0 ? Array.from(selectedBots) : bots.map((bot) => bot.bot_id);

    try {
      await axios.post(`${API_BASE_URL}/bots/action`, {
        action,
        bot_ids: botIds,
        lot_size: bulkLotSize, // Send updated lot size
      });

      alert(`${action} action executed successfully.`);
      fetchBots(); // Refresh bots after action
    } catch (error) {
      console.error(`Error executing ${action}:`, error);
    }
  };

  return (
    <div className="bg-white shadow-md rounded p-6">
      <h2 className="text-xl font-semibold mb-4">Manage Bots</h2>

      {/* Bot Table */}
      <table className="w-full border-collapse border border-gray-300 mb-6">
        <thead>
          <tr className="bg-gray-200">
            <th className="border border-gray-300 p-2">Select</th>
            <th className="border border-gray-300 p-2">ID</th>
            <th className="border border-gray-300 p-2">Bot Name</th>
            <th className="border border-gray-300 p-2">Customer</th>
            <th className="border border-gray-300 p-2">Symbol (Ironbeam)</th>
            <th className="border border-gray-300 p-2">Symbol (Schwab)</th>
            <th className="border border-gray-300 p-2">Lot Size</th>
            <th className="border border-gray-300 p-2">Stop Loss</th>
            <th className="border border-gray-300 p-2">Strategy</th>
            <th className="border border-gray-300 p-2">Live Trading</th>
            <th className="border border-gray-300 p-2">Current Trade</th>
            <th className="border border-gray-300 p-2">Current Bot Trade Status</th>
            <th className="border border-gray-300 p-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {bots.map((bot) => (
            <tr key={bot.bot_id} className="text-center">
              <td className="border border-gray-300 p-2">
                <input
                  type="checkbox"
                  checked={selectedBots.has(bot.bot_id)}
                  onChange={() => toggleBotSelection(bot.bot_id)}
                />
              </td>
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
               <td className={`border border-gray-300 p-2 font-bold ${bot.live_trading ? 'text-green-500' : 'text-red-500'}`}>{bot.live_trading ? "Yes" : "No"}</td>
              <td className={`border border-gray-300 p-2 font-bold ${bot.current_trade_status === 'BUY' ? 'text-green-500' : bot.current_trade_status === 'SELL' ? 'text-red-500' : 'text-gray-500'}`}>{bot.current_trade_status}</td>
              <td className={`border border-gray-300 p-2 font-bold ${bot.current_bot_trade_status === 'BUY' ? 'text-green-500' : bot.current_bot_trade_status === 'SELL' ? 'text-red-500' : 'text-gray-500'}`}>{bot.current_bot_trade_status}</td>
              <td className={`border border-gray-300 p-2 font-bold ${bot.status === 'RUNNING' ? 'text-green-500' : bot.status === 'STOPPED' ? 'text-red-500' : ''}`}>{bot.status}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Action Buttons */}
      <div className="grid grid-cols-4 gap-4 mt-6">
        <button onClick={() => handleAction("START")} className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600" disabled={startInProgress}>{startInProgress ? "Start In Progress..." : "START"}</button>
        <button onClick={() => handleAction("STOP")} className="bg-gray-500 text-white px-4 py-2 rounded hover:bg-gray-600">STOP</button>
        <button onClick={() => handleAction("ENABLE_LIVE_TRADING")} className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600">ENABLE LIVE TRADING</button>
        <button onClick={() => handleAction("DISABLE_LIVE_TRADING")} className="bg-yellow-500 text-white px-4 py-2 rounded hover:bg-yellow-600">DISABLE LIVE TRADING</button>
        <button onClick={() => handleAction("FLAT")} className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600">FLAT</button>
        <button onClick={() => handleAction("FLIP")} className="bg-indigo-500 text-white px-4 py-2 rounded hover:bg-indigo-600">FLIP</button>
        <button onClick={() => handleAction("BUY")} className="bg-green-700 text-white px-4 py-2 rounded hover:bg-green-800">BUY</button>
        <button onClick={() => handleAction("SELL")} className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600">SELL</button>
        <button onClick={() => handleAction("FORCE_BUY")} className="bg-blue-800 text-white px-4 py-2 rounded hover:bg-blue-900">FORCE BUY</button>
        <button onClick={() => handleAction("FORCE_SELL")} className="bg-red-800 text-white px-4 py-2 rounded hover:bg-red-900">FORCE SELL</button>
      </div>

      {/* BULK BUY & BULK SELL with Lot Size Control */}
      <div className="mt-6 flex items-center space-x-4">
        <button onClick={() => handleBulkTrade("BULK_BUY")} className="bg-blue-800 text-white px-4 py-2 rounded hover:bg-blue-900">BULK BUY</button>
        <button onClick={() => handleBulkTrade("BULK_SELL")} className="bg-red-800 text-white px-4 py-2 rounded hover:bg-red-900">BULK SELL</button>
        <button onClick={() => handleAction("BULK_FLAT")} className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600">BULK FLAT</button>
        <button onClick={() => handleBulkTrade("MOVE_FORWARD")} className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600">MOVE FORWARD</button>
        <input type="number" value={bulkLotSize} onChange={(e) => setBulkLotSize(Number(e.target.value))} className="border p-2 w-16 rounded text-center"/>
      </div>
    </div>
  );
}
