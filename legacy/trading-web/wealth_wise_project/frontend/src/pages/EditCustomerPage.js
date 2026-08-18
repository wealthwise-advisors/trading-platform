import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { API_BASE_URL, STATIC_BASE_URL } from "../config";


export default function EditCustomerPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [customer, setCustomer] = useState({
    customer_name: "",
    street: "",
    city: "",
    state: "",
    country: "",
    postal_code: "",
    username: "",
    api_key: "", // Removed password_hash
  });

  useEffect(() => {
    fetchCustomer();
  }, []);

  const fetchCustomer = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/customers/${id}`);
      setCustomer(response.data);
    } catch (error) {
      console.error("Error fetching customer details:", error);
    }
  };

  const updateCustomer = async () => {
    try {
      await axios.put(`${API_BASE_URL}/customers/${id}`, customer);
      navigate("/customers");
    } catch (error) {
      console.error("Error updating customer:", error);
    }
  };

  return (
    <div className="bg-white shadow-md rounded p-6">
      <h2 className="text-xl font-semibold mb-4">Edit Customer</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {Object.keys(customer).map((key) => (
          <input
            key={key}
            type="text"
            placeholder={key.replace("_", " ").toUpperCase()}
            value={customer[key]}
            onChange={(e) => setCustomer({ ...customer, [key]: e.target.value })}
            className="w-full border p-2 rounded"
          />
        ))}
      </div>
      <button
        onClick={updateCustomer}
        className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
      >
        Update Customer
      </button>
    </div>
  );
}
