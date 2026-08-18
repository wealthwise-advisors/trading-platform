import React, { useState, useEffect } from "react";
import axios from "axios";
import { API_BASE_URL } from "../config";

export default function TradesPage() {
  const [trades, setTrades] = useState([]);
  const [sortColumn, setSortColumn] = useState(null);
  const [sortOrder, setSortOrder] = useState("asc");

  useEffect(() => {
    fetchTrades();
  }, []);

  const fetchTrades = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/trades`);
      setTrades(response.data);
    } catch (error) {
      console.error("Error fetching trades:", error);
    }
  };

  const handleSort = (column) => {
    const order = sortColumn === column && sortOrder === "asc" ? "desc" : "asc";
    setSortColumn(column);
    setSortOrder(order);

    const sortedTrades = [...trades].sort((a, b) => {
      if (typeof a[column] === "number") {
        return order === "asc" ? a[column] - b[column] : b[column] - a[column];
      } else {
        return order === "asc"
          ? a[column].toString().localeCompare(b[column].toString())
          : b[column].toString().localeCompare(a[column].toString());
      }
    });

    setTrades(sortedTrades);
  };

  return (
    <div className="bg-white shadow-md rounded p-6">
      <h2 className="text-xl font-semibold mb-4">Trade History</h2>
      <table className="w-full border-collapse border border-gray-300">
        <thead>
          <tr className="bg-gray-200">
            {[
              { label: "ID", key: "trade_id" },
              { label: "Symbol", key: "symbol" },
              { label: "Lot Size", key: "lot_size" },
              { label: "Trade Type", key: "trade_type" },
              { label: "Price", key: "price" },
              { label: "Bot ID", key: "bot_id" },
              { label: "Status", key: "status" },
              { label: "Executed At", key: "executed_at" },
            ].map(({ label, key }) => (
              <th
                key={key}
                className="border border-gray-300 p-2 cursor-pointer"
                onClick={() => handleSort(key)}
              >
                {label} {sortColumn === key ? (sortOrder === "asc" ? "▲" : "▼") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {trades.length > 0 ? (
            trades.map((trade) => (
              <tr key={trade.trade_id} className="text-center">
                <td className="border border-gray-300 p-2">{trade.trade_id}</td>
                <td className="border border-gray-300 p-2">{trade.symbol}</td>
                <td className="border border-gray-300 p-2">{trade.lot_size}</td>
                <td className="border border-gray-300 p-2">{trade.trade_type}</td>
                <td className="border border-gray-300 p-2">{trade.price}</td>
                <td className="border border-gray-300 p-2">{trade.bot_id}</td>
                <td className="border border-gray-300 p-2">{trade.status}</td>
                <td className="border border-gray-300 p-2">{trade.executed_at}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan="8" className="border border-gray-300 p-4 text-center text-gray-600">
                No trades available.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
