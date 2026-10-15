const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function getAuthHeader() {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const api = {
  async postLogin(username, password) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Login failed');
    }
    return res.json();
  },

  async getMe() {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { ...getAuthHeader() }
    });
    if (!res.ok) throw new Error('Failed to fetch user');
    return res.json();
  },

  async getCatalogue() {
    const res = await fetch(`${API_BASE}/catalogue`, {
      headers: { ...getAuthHeader() }
    });
    if (!res.ok) throw new Error('Failed to fetch catalogue');
    return res.json();
  },

  async getBuyerByPhone(phone) {
    const res = await fetch(`${API_BASE}/buyers?phone=${encodeURIComponent(phone)}`, {
      headers: { ...getAuthHeader() }
    });
    if (!res.ok) throw new Error('Failed to search buyer');
    return res.json();
  },

  async createOrder(orderData, idempotencyKey) {
    const headers = {
      'Content-Type': 'application/json',
      ...getAuthHeader()
    };
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    const res = await fetch(`${API_BASE}/orders`, {
      method: 'POST',
      headers,
      body: JSON.stringify(orderData)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create order');
    }
    return res.json();
  },

  async getMyOrders() {
    const res = await fetch(`${API_BASE}/orders/mine`, {
      headers: { ...getAuthHeader() }
    });
    if (!res.ok) throw new Error('Failed to fetch orders');
    return res.json();
  },

  async getUpiQr(orderId, amount) {
    const url = amount 
      ? `${API_BASE}/payments/qr/${orderId}?amount=${amount}`
      : `${API_BASE}/payments/qr/${orderId}`;
    const res = await fetch(url, { headers: { ...getAuthHeader() } });
    if (!res.ok) throw new Error('Failed to load UPI QR');
    return res.json();
  },

  async uploadProof(file) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/payments/upload-proof`, {
      method: 'POST',
      headers: { ...getAuthHeader() },
      body: formData
    });
    if (!res.ok) throw new Error('Proof upload failed');
    return res.json();
  },

  async collectPayment(orderId, amount, method, utr, screenshotFileId, note) {
    const res = await fetch(`${API_BASE}/payments/collect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
      body: JSON.stringify({
        order_id: orderId,
        amount,
        method,
        utr: utr || null,
        screenshot_file_id: screenshotFileId || null,
        note
      })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Payment collection failed');
    }
    return res.json();
  },

  getPdfUrl(orderId) {
    const token = localStorage.getItem('token') || '';
    return `${API_BASE}/payments/pdf/${orderId}?token=${encodeURIComponent(token)}`;
  },

  async downloadPdf(orderId, billNo = 'bill') {
    try {
      const res = await fetch(`${API_BASE}/payments/pdf/${orderId}`, {
        headers: { ...getAuthHeader() }
      });
      if (!res.ok) throw new Error('Failed to download PDF bill');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Bill_${billNo}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => window.URL.revokeObjectURL(url), 2000);
    } catch (err) {
      console.error(err);
      // Fallback: direct window open with query token
      const token = localStorage.getItem('token') || '';
      window.open(`${API_BASE}/payments/pdf/${orderId}?token=${encodeURIComponent(token)}`, '_blank');
    }
  },

  // Admin APIs
  async getSellers() {
    const res = await fetch(`${API_BASE}/admin/sellers`, {
      headers: { ...getAuthHeader() }
    });
    if (!res.ok) throw new Error('Failed to fetch sellers');
    return res.json();
  },

  async createSeller(data) {
    const res = await fetch(`${API_BASE}/admin/sellers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create seller');
    }
    return res.json();
  },

  async toggleSeller(sellerId) {
    const res = await fetch(`${API_BASE}/admin/sellers/${sellerId}/toggle-active`, {
      method: 'PUT',
      headers: { ...getAuthHeader() }
    });
    return res.json();
  },

  async updateStock(itemSizeId, qtyDelta, reason) {
    const res = await fetch(`${API_BASE}/admin/stock`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
      body: JSON.stringify({ item_size_id: itemSizeId, qty_delta: qtyDelta, reason })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to update stock');
    }
    return res.json();
  },

  async createItem(name, price, sizes) {
    const res = await fetch(`${API_BASE}/admin/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
      body: JSON.stringify({ name, price, sizes })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create item');
    }
    return res.json();
  },

  // Admin Dashboard & Reports APIs
  async getDashboardMetrics() {
    const res = await fetch(`${API_BASE}/admin/dashboard-metrics`, {
      headers: { ...getAuthHeader() }
    });
    if (!res.ok) throw new Error('Failed to fetch dashboard metrics');
    return res.json();
  },

  async getItemBySizeReport() {
    const res = await fetch(`${API_BASE}/admin/reports/item-by-size`, {
      headers: { ...getAuthHeader() }
    });
    if (!res.ok) throw new Error('Failed to fetch item sales report');
    return res.json();
  },

  async getNagarWiseReport() {
    const res = await fetch(`${API_BASE}/admin/reports/nagar-wise`, {
      headers: { ...getAuthHeader() }
    });
    if (!res.ok) throw new Error('Failed to fetch nagar report');
    return res.json();
  },

  async getAllAdminOrders(params = {}) {
    const query = new URLSearchParams(params).toString();
    const url = query ? `${API_BASE}/admin/orders?${query}` : `${API_BASE}/admin/orders`;
    const res = await fetch(url, {
      headers: { ...getAuthHeader() }
    });
    if (!res.ok) throw new Error('Failed to fetch orders');
    return res.json();
  },

  async cancelOrder(orderId, reason) {
    const res = await fetch(`${API_BASE}/admin/orders/${orderId}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
      body: JSON.stringify({ reason })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Cancellation failed');
    }
    return res.json();
  },

  async revertOrder(orderId, reason = '') {
    const res = await fetch(`${API_BASE}/admin/orders/${orderId}/revert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
      body: JSON.stringify({ reason: reason || 'Restored by admin' })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Revert order failed');
    }
    return res.json();
  },

  async getAuditLogs() {
    const res = await fetch(`${API_BASE}/admin/audit-log`, {
      headers: { ...getAuthHeader() }
    });
    if (!res.ok) throw new Error('Failed to fetch audit log');
    return res.json();
  },

  getCsvExportUrl() {
    const token = localStorage.getItem('token');
    return token ? `${API_BASE}/admin/export/csv?token=${token}` : `${API_BASE}/admin/export/csv`;
  },

  getExcelExportUrl() {
    const token = localStorage.getItem('token');
    return token ? `${API_BASE}/admin/export/excel?token=${token}` : `${API_BASE}/admin/export/excel`;
  },

  getItemSalesExcelUrl() {
    const token = localStorage.getItem('token');
    return token ? `${API_BASE}/admin/export/excel-items?token=${token}` : `${API_BASE}/admin/export/excel-items`;
  },

  getNagarSalesExcelUrl() {
    const token = localStorage.getItem('token');
    return token ? `${API_BASE}/admin/export/excel-nagars?token=${token}` : `${API_BASE}/admin/export/excel-nagars`;
  }
};
