import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { FaTrash } from "react-icons/fa"; // Import delete icon
import { API_BASE_URL, STATIC_BASE_URL } from "../config";


export default function CustomersPage() {
  const [customers, setCustomers] = useState([]);
  const [newCustomer, setNewCustomer] = useState({
    customer_name: "",
    street: "",
    city: "",
    state: "",
    country: "",
    postal_code: "",
    username: "",
    password_hash: "",
    api_key: "",
  });

  useEffect(() => {
    fetchCustomers();
  }, []);

  const fetchCustomers = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/customers`);
      setCustomers(response.data);
    } catch (error) {
      console.error("Error fetching customers:", error);
    }
  };

  const addCustomer = async () => {
    if (!newCustomer.customer_name || !newCustomer.street || !newCustomer.city) {
      alert("Please fill in all required fields.");
      return;
    }
    try {
      await axios.post(`${API_BASE_URL}/customers`, newCustomer);
      setNewCustomer({
        customer_name: "",
        street: "",
        city: "",
        state: "",
        country: "",
        postal_code: "",
        username: "",
        password_hash: "",
        api_key: "",
      });
      fetchCustomers();
    } catch (error) {
      console.error("Error adding customer:", error);
    }
  };

  const deleteCustomer = async (customerId) => {
    if (!window.confirm("Are you sure you want to delete this customer?")) return;

    try {
      await axios.delete(`${API_BASE_URL}/customers/${customerId}`);
      setCustomers(customers.filter((customer) => customer.customer_id !== customerId)); // Update UI
    } catch (error) {
      console.error("Error deleting customer:", error);
    }
  };

  return (
    <div className="bg-white shadow-md rounded p-6">
      <h2 className="text-xl font-semibold mb-4">Manage Customers</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <input
          type="text"
          placeholder="Customer Name"
          value={newCustomer.customer_name}
          onChange={(e) => setNewCustomer({ ...newCustomer, customer_name: e.target.value })}
          className="w-full border p-2 rounded"
        />
        <input
          type="text"
          placeholder="Street"
          value={newCustomer.street}
          onChange={(e) => setNewCustomer({ ...newCustomer, street: e.target.value })}
          className="w-full border p-2 rounded"
        />
        <input
          type="text"
          placeholder="City"
          value={newCustomer.city}
          onChange={(e) => setNewCustomer({ ...newCustomer, city: e.target.value })}
          className="w-full border p-2 rounded"
        />
        <input
          type="text"
          placeholder="State"
          value={newCustomer.state}
          onChange={(e) => setNewCustomer({ ...newCustomer, state: e.target.value })}
          className="w-full border p-2 rounded"
        />
        <input
          type="text"
          placeholder="Country"
          value={newCustomer.country}
          onChange={(e) => setNewCustomer({ ...newCustomer, country: e.target.value })}
          className="w-full border p-2 rounded"
        />
        <input
          type="text"
          placeholder="Postal Code"
          value={newCustomer.postal_code}
          onChange={(e) => setNewCustomer({ ...newCustomer, postal_code: e.target.value })}
          className="w-full border p-2 rounded"
        />
        <input
          type="text"
          placeholder="Username"
          value={newCustomer.username}
          onChange={(e) => setNewCustomer({ ...newCustomer, username: e.target.value })}
          className="w-full border p-2 rounded"
        />
        <input
          type="password"
          placeholder="Password Hash"
          value={newCustomer.password_hash}
          onChange={(e) => setNewCustomer({ ...newCustomer, password_hash: e.target.value })}
          className="w-full border p-2 rounded"
        />
        <input
          type="text"
          placeholder="API Key"
          value={newCustomer.api_key}
          onChange={(e) => setNewCustomer({ ...newCustomer, api_key: e.target.value })}
          className="w-full border p-2 rounded"
        />
      </div>
      <button
        onClick={addCustomer}
        className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
      >
        Add Customer
      </button>

      {/* Customer Table */}
      <table className="w-full border-collapse border border-gray-300 mt-6">
        <thead>
          <tr className="bg-gray-200">
            <th className="border border-gray-300 p-2">ID</th>
            <th className="border border-gray-300 p-2">Customer Name</th>
            <th className="border border-gray-300 p-2">Street</th>
            <th className="border border-gray-300 p-2">City</th>
            <th className="border border-gray-300 p-2">State</th>
            <th className="border border-gray-300 p-2">Country</th>
            <th className="border border-gray-300 p-2">Postal Code</th>
            <th className="border border-gray-300 p-2">Username</th>
            <th className="border border-gray-300 p-2">API Key</th>
            <th className="border border-gray-300 p-2">Actions</th> {/* Delete Column */}
          </tr>
        </thead>
        <tbody>
          {customers.length > 0 ? (
            customers.map((customer) => (
              <tr key={customer.customer_id} className="text-center">
                <td className="border border-gray-300 p-2">
                  <Link to={`/customers/edit/${customer.customer_id}`} className="text-blue-600 underline">
                    {customer.customer_id}
                  </Link>
                </td>
                <td className="border border-gray-300 p-2">{customer.customer_name}</td>
                <td className="border border-gray-300 p-2">{customer.street}</td>
                <td className="border border-gray-300 p-2">{customer.city}</td>
                <td className="border border-gray-300 p-2">{customer.state}</td>
                <td className="border border-gray-300 p-2">{customer.country}</td>
                <td className="border border-gray-300 p-2">{customer.postal_code}</td>
                <td className="border border-gray-300 p-2">{customer.username}</td>
                <td className="border border-gray-300 p-2">{customer.api_key}</td>
                <td className="border border-gray-300 p-2">
                  <button onClick={() => deleteCustomer(customer.customer_id)} className="text-red-500 hover:text-red-700">
                    <FaTrash />
                  </button>
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan="10" className="border border-gray-300 p-4 text-center text-gray-600">
                No customers found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
