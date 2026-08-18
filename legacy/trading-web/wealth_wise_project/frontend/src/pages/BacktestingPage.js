import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { API_BASE_URL, STATIC_BASE_URL } from "../config";


export default function BacktestingPage() {
  const [params, setParams] = useState({
    symbol: "",
    start_date: "",
    end_date: "",
    start_time: "09:30", // Default start time
    end_time: "16:00", // Default end time
    interval: "1m",
    lot_size: 50,
    stop_loss_adjust: 200,
    strategy: "Strategy_One",
  });

  const [backtestHtml, setBacktestHtml] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [loading, setLoading] = useState(false); // 🔄 New state for loading

const INSTRUMENTS = [
  { symbol: "ES", name: "E-mini S&P 500", value: 50, stop_loss: 200 },
  { symbol: "NQ", name: "E-mini NASDAQ-100", value: 20, stop_loss: 200 },
  { symbol: "GC", name: "Gold Futures", value: 100, stop_loss: 200 },
  { symbol: "CL", name: "Crude Oil", value: 10, stop_loss: 2 },
  { symbol: "CT", name: "Cotton", value: 5, stop_loss: 2 },
  { symbol: "6B", name: "British Pound", value: 5, stop_loss: 2 },
  { symbol: "6E", name: "Euro FX", value: 6.25, stop_loss: 1 },
  { symbol: "6C", name: "Canadian Dollar", value: 6.25, stop_loss: 2 },
  { symbol: "6A", name: "Australian Dollar", value: 5, stop_loss: 2 },
  { symbol: "6N", name: "New Zealand Dollar", value: 5, stop_loss: 5 },
  { symbol: "6J", name: "Japanese Yen", value: 6.25, stop_loss: 1 },
  { symbol: "6S", name: "Swiss Franc", value: 6.25, stop_loss: 1 },
  { symbol: "BZ", name: "Brent Crude Oil", value: 10, stop_loss: 2 },
  { symbol: "CC", name: "Cocoa", value: 10, stop_loss: 100 },
  { symbol: "LE", name: "Live Cattle", value: 10, stop_loss: 5 },
  { symbol: "HG", name: "Copper", value: 12.5, stop_loss: 2.5 },
  { symbol: "HO", name: "Heating Oil", value: 4.2, stop_loss: 1000 },
  { symbol: "KC", name: "Coffee", value: 18.75, stop_loss: 8 },
  { symbol: "HE", name: "Lean Hogs", value: 10, stop_loss: 10 },
  { symbol: "NG", name: "Natural Gas", value: 10, stop_loss: 3 },
  { symbol: "PL", name: "Platinum", value: 10, stop_loss: 3 },
  { symbol: "OJ", name: "Orange Juice", value: 7.5, stop_loss: 10 },
  { symbol: "RTY", name: "E-mini Russell 2000", value: 5, stop_loss: 200 },
  { symbol: "SB", name: "Sugar", value: 11.2, stop_loss: 200 },
  { symbol: "SI", name: "Silver", value: 25, stop_loss: 4 },
  { symbol: "TN", name: "10-Year Treasury Note", value: 15.63, stop_loss: 3 },
  { symbol: "ZB", name: "30-Year Treasury Bond", value: 31.25, stop_loss: 3 },
  { symbol: "ZC", name: "Corn", value: 12.5, stop_loss: 3 },
  { symbol: "ZL", name: "Soybean Oil", value: 6, stop_loss: 3 },
  { symbol: "ZS", name: "Soybeans", value: 12.5, stop_loss: 5 },
  { symbol: "ZW", name: "Wheat", value: 12.5, stop_loss: 5 },
  { symbol: "RB", name: "Gasoline", value: 4.2, stop_loss: 3 },
];

    const timeoutRef = useRef(null);
    const intervalRef = useRef(null);

    // Clear timers on unmount
    useEffect(() => {
      return () => {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        if (intervalRef.current) clearInterval(intervalRef.current);
      };
    }, []);




    const scheduleMinuteAlignedBacktest = () => {
      // Clear old timers if any
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (intervalRef.current) clearInterval(intervalRef.current);

      const now = new Date();
      const seconds = now.getSeconds();
      const ms = now.getMilliseconds();

      // Time until next full minute + 1 second
      let delay = (60 - seconds) * 1000 - ms + 1000; // e.g., from 09:44:30 → ~31s to 09:45:01
      if (delay < 0) delay += 60 * 1000; // safety

      timeoutRef.current = setTimeout(async () => {
        await runBacktest(); // first aligned run: 09:45:01

        // Then fixed every 60s: 09:46:01, 09:47:01, ...
        intervalRef.current = setInterval(() => {
          runBacktest();
        }, 60 * 1000);
      }, delay);
    };


  const validateInputs = () => {
    const { interval, start_date, end_date, lot_size, stop_loss_adjust, start_time, end_time } = params;
    const startDate = new Date(start_date);
    const endDate = new Date(end_date);
    const dateDiff = (endDate - startDate) / (1000 * 60 * 60 * 24);

    if (!params.symbol) return "Symbol is required.";
    if (!start_date || !end_date) return "Both Start and End Dates are required.";
    if (startDate > endDate) return "Start Date cannot be after End Date.";
    if (!start_time || !end_time) return "Start Time and End Time are required.";
    if (isNaN(lot_size) || lot_size <= 0) return "Lot Size must be a positive integer.";
    if (isNaN(stop_loss_adjust)) return "Stop Loss Adjust must be a number.";

    const intervalLimit = {
      "1m": 7,
      "5m": 50,
      "10m": 50,
      "15m": 50,
      "30m": 50,
    };

    if (interval in intervalLimit && dateDiff > intervalLimit[interval]) {
      return `Please select a date range within ${intervalLimit[interval]} days for ${interval}.`;
    }

    return null;
  };

    const handleInstrumentSelect = (e) => {
      const selectedSymbol = e.target.value;
      const instrument = INSTRUMENTS.find((inst) => inst.symbol === selectedSymbol);

      // Get today's date in local time
      const today = new Date();
      const formattedDate = today.toISOString().split("T")[0]; // This can cause the UTC issue

      // Convert to local date
      const localDate = new Date(today.getTime() - today.getTimezoneOffset() * 60000)
        .toISOString()
        .split("T")[0];

      if (instrument) {
        setParams({
          symbol: `/${selectedSymbol}`,
          start_date: localDate,  // ✅ Now correctly shows the local date
          end_date: localDate,    // ✅ Fixes the next-day issue
          start_time: "08:30",
          end_time: "14:45",
          interval: "1m",
          lot_size: instrument.value,
          stop_loss_adjust: instrument.stop_loss,
          strategy: "Strategy_One",
        });
      }
    };



  const handleChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({
      ...prev,
      [name]: name === "lot_size" || name === "stop_loss_adjust" ? parseFloat(value) || 0 : value,
    }));
  };

    const runBacktest = async () => {
      const validationError = validateInputs();
      if (validationError) {
        setErrorMessage(validationError);
        return false; // ❗ don't schedule if bad inputs
      }

      setLoading(true);
      setErrorMessage("");

      try {
        const response = await axios.post(`${API_BASE_URL}/backtest`, params);
        setBacktestHtml(response.data.backtest_url);
        return true; // ✅ success
      } catch (error) {
        console.error("Error running backtest:", error);
        setErrorMessage("Failed to run backtest. Please try again.");
        return false; //
      } finally {
        setLoading(false);
      }
    };

     const handleRunBacktestClick = async () => {
       const ok = await runBacktest(); // run immediately (e.g., 09:44:30)
       if (ok) {
         scheduleMinuteAlignedBacktest(); // schedule 09:45:01, 09:46:01, ...
       }
     };


  return (
    <div className="bg-white shadow-md rounded p-6">
      <h2 className="text-xl font-semibold mb-4">Backtesting</h2>

      {errorMessage && <p className="text-red-500 font-semibold mb-4">{errorMessage}</p>}


    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Instrument Selection Dropdown */}
      <div>
        <label className="block font-semibold">Select Instrument:</label>
        <select
          name="instrument"
          onChange={handleInstrumentSelect}
          className="border p-2 rounded w-full"
        >
          <option value="">Select Instrument</option>
          {INSTRUMENTS.map((inst) => (
            <option key={inst.symbol} value={inst.symbol}>
              /{inst.symbol} - {inst.name}
            </option>
          ))}
        </select>
      </div>
    </div>

      {/* Input Fields */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block font-semibold">Symbol:</label>
          <input
            type="text"
            name="symbol"
            value={params.symbol}
            onChange={handleChange}
            className="border p-2 rounded w-full"
            placeholder="Enter Symbol"
          />
        </div>

        <div>
          <label className="block font-semibold">Start Date:</label>
          <input
            type="date"
            name="start_date"
            value={params.start_date}
            onChange={handleChange}
            className="border p-2 rounded w-full"
          />
        </div>

        <div>
          <label className="block font-semibold">End Date:</label>
          <input
            type="date"
            name="end_date"
            value={params.end_date}
            onChange={handleChange}
            className="border p-2 rounded w-full"
          />
        </div>

        <div>
          <label className="block font-semibold">Start Time:</label>
          <input
            type="time"
            name="start_time"
            value={params.start_time}
            onChange={handleChange}
            className="border p-2 rounded w-full"
          />
        </div>

        <div>
          <label className="block font-semibold">End Time:</label>
          <input
            type="time"
            name="end_time"
            value={params.end_time}
            onChange={handleChange}
            className="border p-2 rounded w-full"
          />
        </div>

        <div>
          <label className="block font-semibold">Lot Size:</label>
          <input
            type="number"
            name="lot_size"
            value={params.lot_size}
            onChange={handleChange}
            className="border p-2 rounded w-full"
            min="1"
          />
        </div>

        <div>
          <label className="block font-semibold">Stop Loss Adjust:</label>
          <input
            type="number"
            name="stop_loss_adjust"
            value={params.stop_loss_adjust}
            onChange={handleChange}
            className="border p-2 rounded w-full"
          />
        </div>

        <div>
          <label className="block font-semibold">Strategy:</label>
          <select
            name="strategy"
            value={params.strategy}
            onChange={handleChange}
            className="border p-2 rounded w-full"
          >
            <option value="Strategy_One">Strategy One</option>
            <option value="Strategy_Two">Strategy Two</option>
            <option value="Strategy_Three">Strategy Three</option>
            <option value="Strategy_Four">Strategy Four</option>
            <option value="Strategy_Five">Strategy Five</option>
          </select>
        </div>

        <div>
          <label className="block font-semibold">Interval:</label>
          <select
            name="interval"
            value={params.interval}
            onChange={handleChange}
            className="border p-2 rounded w-full"
          >
            <option value="1m">1 Minute (Max: 7 Days)</option>
            <option value="5m">5 Minutes (Max: 50 Days)</option>
            <option value="10m">10 Minutes (Max: 50 Days)</option>
            <option value="15m">15 Minutes (Max: 50 Days)</option>
            <option value="30m">30 Minutes (Max: 50 Days)</option>
            <option value="45m">45 Minutes</option>
            <option value="75m">75 Minutes</option>
            <option value="90m">90 Minutes</option>
            <option value="1h">1 Hour</option>
            <option value="2h">2 Hours</option>
            <option value="3h">3 Hours</option>
            <option value="4h">4 Hours</option>
            <option value="1d">1 Day</option>
          </select>
        </div>
      </div>

      {/* Run Backtest Button & Loading Spinner */}
      <button
        onClick={handleRunBacktestClick}
        disabled={loading}
        className="bg-blue-500 text-white px-4 py-2 mt-4 rounded hover:bg-blue-600 flex items-center"
      >
        {loading && <span className="animate-spin mr-2">🔄</span>}
        {loading ? "Running Backtest..." : "Run Backtest"}
      </button>

      {/* Backtest Results */}
      {backtestHtml && (
        <iframe
          src={`${STATIC_BASE_URL}/${backtestHtml}`}
          title="Backtest Results"
          className="w-full h-screen mt-4"
        />
      )}
    </div>
  );
}
