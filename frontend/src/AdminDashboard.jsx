import React, { useState, useEffect } from 'react';
import { api } from './api';
import {
  BarChart3, Package, MapPin, Users, Boxes, FileText,
  AlertTriangle, Download, RefreshCw, XCircle, Search, PlusCircle,
  Banknote, QrCode, Clock, ShieldAlert, CheckCircle2, ChevronRight, RotateCcw
} from 'lucide-react';

export default function AdminDashboard({ user }) {
  const [adminTab, setAdminTab] = useState('overview'); // overview, all_orders, item_sales, nagars, sellers, stock_mgmt, audit
  const [metrics, setMetrics] = useState(null);
  const [itemReport, setItemReport] = useState([]);
  const [nagarReport, setNagarReport] = useState([]);
  const [sellersList, setSellersList] = useState([]);
  const [allOrders, setAllOrders] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(false);

  // Search & Filter
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Cancel order modal
  const [cancellingOrder, setCancellingOrder] = useState(null);
  const [cancelReason, setCancelReason] = useState('');

  // New Seller Modal
  const [showAddSeller, setShowAddSeller] = useState(false);
  const [sellerName, setSellerName] = useState('');
  const [sellerUsername, setSellerUsername] = useState('');
  const [sellerPhone, setSellerPhone] = useState('');
  const [sellerPassword, setSellerPassword] = useState('');

  // Stock Adjustment Modal
  const [adjustingStockItem, setAdjustingStockItem] = useState(null);
  const [stockDelta, setStockDelta] = useState(0);
  const [stockReason, setStockReason] = useState('');

  // New Nagar
  const [newNagarName, setNewNagarName] = useState('');

  useEffect(() => {
    loadAllData();
  }, []);

  const loadAllData = async () => {
    setLoading(true);
    try {
      const [m, ir, nr, sel, ord] = await Promise.all([
        api.getDashboardMetrics(),
        api.getItemBySizeReport(),
        api.getNagarWiseReport(),
        api.getSellers(),
        api.getAllAdminOrders()
      ]);
      setMetrics(m);
      setItemReport(ir);
      setNagarReport(nr);
      setSellersList(sel);
      setAllOrders(ord);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancelOrder = async () => {
    if (!cancellingOrder || !cancelReason.trim()) {
      alert("Please provide a cancellation reason.");
      return;
    }
    try {
      setLoading(true);
      await api.cancelOrder(cancellingOrder.id, cancelReason.trim());
      alert("Order cancelled successfully. Stock returned to pool.");
      setCancellingOrder(null);
      setCancelReason('');
      loadAllData();
    } catch (err) {
      alert(`Cancellation failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRevertOrder = async (order) => {
    const reason = window.prompt(`Are you sure you want to revert/restore Order ${order.bill_no} back to Active?\nStock will be re-deducted from the pool.\n\nReason for reverting:`, "Restored by admin");
    if (reason === null) return;
    try {
      setLoading(true);
      await api.revertOrder(order.id, reason.trim() || 'Restored by admin');
      alert(`Order ${order.bill_no} has been restored to Active. Stock re-deducted successfully.`);
      loadAllData();
    } catch (err) {
      alert(`Failed to revert order: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSeller = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      await api.createSeller({
        name: sellerName.trim(),
        username: sellerUsername.trim(),
        phone: sellerPhone.trim(),
        password: sellerPassword
      });
      alert("Seller created successfully!");
      setShowAddSeller(false);
      setSellerName('');
      setSellerUsername('');
      setSellerPhone('');
      setSellerPassword('');
      const updatedSellers = await api.getSellers();
      setSellersList(updatedSellers);
    } catch (err) {
      alert(`Failed to create seller: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleSeller = async (id) => {
    try {
      await api.toggleSeller(id);
      const updatedSellers = await api.getSellers();
      setSellersList(updatedSellers);
    } catch (err) {
      alert(`Toggle failed: ${err.message}`);
    }
  };

  const handleStockUpdate = async () => {
    if (!adjustingStockItem || stockDelta === 0) {
      alert("Please specify a non-zero quantity change.");
      return;
    }
    try {
      setLoading(true);
      await api.updateStock(adjustingStockItem.item_size_id, Number(stockDelta), stockReason || 'Admin adjustment');
      alert("Stock updated successfully!");
      setAdjustingStockItem(null);
      setStockDelta(0);
      setStockReason('');
      loadAllData();
    } catch (err) {
      alert(`Stock update failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleAddNagar = async (e) => {
    e.preventDefault();
    if (!newNagarName.trim()) return;
    try {
      setLoading(true);
      await api.createNagar(newNagarName.trim());
      setNewNagarName('');
      const nr = await api.getNagarWiseReport();
      setNagarReport(nr);
      alert("Nagar added successfully!");
    } catch (err) {
      alert(`Failed to add Nagar: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const loadAudit = async () => {
    try {
      const logs = await api.getAuditLogs();
      setAuditLogs(logs);
    } catch (err) {
      console.error(err);
    }
  };

  const filteredOrders = allOrders.filter(o => {
    const matchesSearch = !searchTerm || (
      o.bill_no.toLowerCase().includes(searchTerm.toLowerCase()) ||
      o.buyer_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      o.buyer_phone.includes(searchTerm)
    );
    const matchesStatus = !statusFilter || o.payment_status === statusFilter || o.order_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const cancelledOrders = allOrders.filter(o => o.order_status === 'Cancelled');
  const filteredCancelledOrders = cancelledOrders.filter(o =>
    o.bill_no.toLowerCase().includes(searchTerm.toLowerCase()) ||
    o.buyer_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    o.buyer_phone.includes(searchTerm)
  );

  const navTabs = [
    { key: 'overview', label: 'Overview', icon: BarChart3 },
    { key: 'all_orders', label: `All Orders (${allOrders.length})`, icon: Package },
    { key: 'cancelled_orders', label: `Cancelled (${cancelledOrders.length})`, icon: XCircle },
    { key: 'item_sales', label: 'Item Sales', icon: Boxes },
    { key: 'nagars', label: 'Nagars', icon: MapPin },
    { key: 'sellers', label: `Sellers (${sellersList.length})`, icon: Users },
    { key: 'stock_mgmt', label: 'Stock Pool', icon: Boxes },
    { key: 'audit', label: 'Audit Trail', icon: FileText }
  ];

  return (
    <div style={{ padding: '16px' }}>
      {/* Clean Professional Subnav */}
      <div className="admin-subnav" style={{
        display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '12px',
        borderBottom: '1px solid var(--border)', marginBottom: '16px', scrollbarWidth: 'none',
        WebkitOverflowScrolling: 'touch'
      }}>
        {navTabs.map(t => {
          const Icon = t.icon;
          const isActive = adminTab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => {
                setAdminTab(t.key);
                if (t.key === 'audit') loadAudit();
              }}
              className={`btn ${isActive ? 'btn-primary' : 'btn-secondary'}`}
              style={{
                minHeight: '40px', height: '40px', fontSize: '0.86rem', padding: '0 16px',
                whiteSpace: 'nowrap', display: 'inline-flex', alignItems: 'center', gap: '8px',
                borderRadius: '9999px', fontWeight: isActive ? '700' : '600',
                flexShrink: 0, width: 'auto', minWidth: 'max-content'
              }}
            >
              <Icon size={16} />
              <span>{t.label}</span>
            </button>
          );
        })}
      </div>

      {/* ---------------- 1. OVERVIEW METRICS ---------------- */}
      {adminTab === 'overview' && metrics && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: '700' }}>Organizer Dashboard Overview</h2>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <button onClick={loadAllData} className="btn btn-secondary" style={{ height: '38px', minHeight: '38px', padding: '0 12px' }}>
                <RefreshCw size={15} /> Refresh
              </button>
              <a
                href={api.getExcelExportUrl()}
                download
                className="btn btn-primary"
                style={{ height: '38px', minHeight: '38px', padding: '0 14px', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                title="Download all orders with user details, cash/upi columns & nagar"
              >
                <Download size={15} /> Orders Excel (.xlsx)
              </a>
              <a
                href={api.getItemSalesExcelUrl()}
                download
                className="btn btn-secondary"
                style={{ height: '38px', minHeight: '38px', padding: '0 12px', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                title="Download item with size-wise quantity sold and unit price without stock"
              >
                <Download size={15} /> Item Sales (.xlsx)
              </a>
              <a
                href={api.getNagarSalesExcelUrl()}
                download
                className="btn btn-secondary"
                style={{ height: '38px', minHeight: '38px', padding: '0 12px', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                title="Download Nagar-wise sales distribution"
              >
                <Download size={15} /> Nagar Sales (.xlsx)
              </a>
            </div>
          </div>

          {/* Key Stat Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', marginBottom: '20px' }}>
            <div className="card" style={{ borderLeft: '4px solid var(--primary)' }}>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Total Sales Value</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 'bold', color: 'var(--primary)' }}>₹{metrics.total_sales_value}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                {metrics.total_orders} Active Orders ({metrics.today_orders} today)
              </div>
            </div>

            <div className="card" style={{ borderLeft: '4px solid var(--success)' }}>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Total Collections</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 'bold', color: 'var(--success)' }}>₹{metrics.total_collected}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', gap: '10px' }}>
                <span>Cash: <strong>₹{metrics.cash_total}</strong></span>
                <span>•</span>
                <span>UPI: <strong>₹{metrics.upi_total}</strong></span>
              </div>
            </div>

            <div className="card" style={{ borderLeft: '4px solid var(--warning)' }}>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Pending Balances</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 'bold', color: '#b45309' }}>₹{metrics.pending_balance}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                Across {metrics.pending_orders_count} pending orders
              </div>
            </div>

            <div
              className="card"
              style={{ borderLeft: '4px solid #ef4444', cursor: 'pointer', transition: 'all 0.2s ease' }}
              onClick={() => setAdminTab('cancelled_orders')}
              title="Click to view & revert cancelled orders"
            >
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
                <span>Cancelled Orders</span>
                <span style={{ fontSize: '0.75rem', color: '#dc2626', fontWeight: 'bold' }}>View & Revert →</span>
              </div>
              <div style={{ fontSize: '1.6rem', fontWeight: 'bold', color: '#b91c1c' }}>{metrics.cancelled_orders}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>Click to view or revert</div>
            </div>
          </div>

          {/* Low Stock Alerts */}
          <div className="card" style={{ marginBottom: '20px' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: '700', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={18} color="#ea580c" /> Low Stock Alerts (5 or fewer units remaining)
            </h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {itemReport.flatMap(it =>
                it.sizes.filter(s => s.is_low_stock).map(s => (
                  <span
                    key={`${it.item_id}-${s.size}`}
                    style={{
                      background: s.available_stock === 0 ? '#fee2e2' : '#fef3c7',
                      color: s.available_stock === 0 ? '#b91c1c' : '#92400e',
                      padding: '6px 12px', borderRadius: '6px', fontSize: '0.82rem', fontWeight: '600'
                    }}
                  >
                    {it.item_name} (Size {s.size}): {s.available_stock} left
                  </span>
                ))
              )}
            </div>
          </div>

          {/* Nagar-wise snapshot */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
                <MapPin size={18} color="var(--primary)" /> Nagar-wise Sales Distribution
              </h3>
              <a
                href={api.getNagarSalesExcelUrl()}
                download
                className="btn btn-secondary"
                style={{ height: '32px', minHeight: '32px', padding: '0 12px', fontSize: '0.8rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                title="Download Nagar-wise sales as Excel"
              >
                <Download size={13} /> Export Nagar Sales (.xlsx)
              </a>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', borderBottom: '2px solid var(--border)' }}>
                    <th style={{ padding: '8px 10px' }}>Nagar</th>
                    <th style={{ padding: '8px 10px' }}>Orders</th>
                    <th style={{ padding: '8px 10px' }}>Sales (₹)</th>
                    <th style={{ padding: '8px 10px' }}>Paid (₹)</th>
                    <th style={{ padding: '8px 10px' }}>Pending (₹)</th>
                  </tr>
                </thead>
                <tbody>
                  {nagarReport.map(n => (
                    <tr key={n.nagar_id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '8px 10px', fontWeight: '600' }}>{n.nagar_name}</td>
                      <td style={{ padding: '8px 10px' }}>{n.order_count}</td>
                      <td style={{ padding: '8px 10px', fontWeight: 'bold' }}>₹{n.total_sales}</td>
                      <td style={{ padding: '8px 10px', color: 'var(--success)' }}>₹{n.total_paid}</td>
                      <td style={{ padding: '8px 10px', color: n.total_balance > 0 ? 'var(--danger)' : 'var(--text-muted)' }}>
                        ₹{n.total_balance}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ---------------- 2. ALL ORDERS WITH SEARCH & CANCEL ---------------- */}
      {adminTab === 'all_orders' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: '700' }}>All Orders & Invoices</h3>
            <button onClick={loadAllData} className="btn btn-secondary" style={{ height: '36px', minHeight: '36px', padding: '0 12px' }}>
              <RefreshCw size={14} /> Refresh
            </button>
          </div>

          {/* Search bar & filter */}
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '8px', marginBottom: '14px' }}>
            <input
              className="form-control"
              type="text"
              placeholder="Search Bill No, Buyer Name, Phone..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            <select
              className="form-control"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="Paid">Paid</option>
              <option value="Partial">Partial</option>
              <option value="Unpaid">Unpaid</option>
              <option value="Cancelled">Cancelled</option>
            </select>
          </div>

          {filteredOrders.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
              No orders found matching the filter criteria.
            </div>
          ) : (
            filteredOrders.map(o => (
              <div key={o.id} className="card" style={{ opacity: o.order_status === 'Cancelled' ? 0.7 : 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span style={{ fontWeight: 'bold' }}>{o.bill_no}</span>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <span className={`chip chip-${o.payment_status.toLowerCase()}`}>
                      {o.payment_status}
                    </span>
                    {o.order_status === 'Cancelled' && (
                      <span className="chip chip-cancelled">Cancelled</span>
                    )}
                  </div>
                </div>

                <div style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                  <strong>{o.buyer_name}</strong> ({o.buyer_phone}) • {o.nagar_name || 'N/A'} • Seller: {o.seller_name}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', marginBottom: '10px' }}>
                  <span>Total: <strong>₹{o.total}</strong></span>
                  <span>Paid: ₹{o.paid_amount}</span>
                  <span style={{ color: o.balance > 0 ? 'var(--danger)' : 'var(--success)', fontWeight: 'bold' }}>
                    Balance: ₹{o.balance}
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={() => api.downloadPdf(o.id, o.bill_no)}
                    className="btn btn-secondary"
                    style={{ flex: 1, height: '36px', minHeight: '36px', fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                  >
                    <Download size={14} /> Download PDF
                  </button>

                  {o.order_status === 'Active' ? (
                    <button
                      className="btn btn-secondary"
                      style={{ color: 'var(--danger)', height: '36px', minHeight: '36px', fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                      onClick={() => setCancellingOrder(o)}
                    >
                      <XCircle size={14} /> Cancel Order
                    </button>
                  ) : (
                    <button
                      className="btn btn-secondary"
                      style={{ color: 'var(--primary)', borderColor: 'var(--primary)', height: '36px', minHeight: '36px', fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                      onClick={() => handleRevertOrder(o)}
                      disabled={loading}
                    >
                      <RotateCcw size={14} /> Revert Order
                    </button>
                  )}
                </div>

                {o.cancel_reason && (
                  <div style={{ marginTop: '8px', fontSize: '0.8rem', color: 'var(--danger)', background: '#fee2e2', padding: '6px 10px', borderRadius: '6px' }}>
                    <strong>Cancellation Reason:</strong> {o.cancel_reason}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* ---------------- 2b. CANCELLED ORDERS VIEW (REVERT CAPABILITY) ---------------- */}
      {adminTab === 'cancelled_orders' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: '700', color: '#b91c1c', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
                <XCircle size={20} color="#b91c1c" /> Cancelled Orders ({cancelledOrders.length})
              </h3>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Stock was returned to pool. Click "Revert / Restore Order" to restore to Active with stock re-reservation.
              </div>
            </div>
            <button onClick={loadAllData} className="btn btn-secondary" style={{ height: '36px', minHeight: '36px', padding: '0 12px' }}>
              <RefreshCw size={14} /> Refresh
            </button>
          </div>

          {/* Search bar */}
          <div style={{ marginBottom: '14px' }}>
            <input
              className="form-control"
              type="text"
              placeholder="Search Cancelled Bill No, Buyer Name, Phone..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          {filteredCancelledOrders.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '36px 16px' }}>
              <CheckCircle2 size={36} color="var(--success)" style={{ margin: '0 auto 8px', display: 'block' }} />
              <strong style={{ fontSize: '1rem', color: 'var(--text-main)' }}>No Cancelled Orders</strong>
              <div style={{ fontSize: '0.85rem', marginTop: '4px' }}>All orders are active. Any orders cancelled will appear here for audit and restoration.</div>
            </div>
          ) : (
            filteredCancelledOrders.map(o => (
              <div key={o.id} className="card" style={{ borderLeft: '4px solid #ef4444', backgroundColor: '#fffafb' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span style={{ fontWeight: 'bold', fontSize: '1rem' }}>{o.bill_no}</span>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <span className="chip chip-cancelled">Cancelled</span>
                    <span className={`chip chip-${o.payment_status.toLowerCase()}`}>{o.payment_status}</span>
                  </div>
                </div>

                <div style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                  <strong>{o.buyer_name}</strong> ({o.buyer_phone}) • {o.nagar_name || 'N/A'} • Seller: <strong>{o.seller_name}</strong>
                </div>

                <div style={{ fontSize: '0.84rem', color: '#4b5563', marginBottom: '8px', background: '#f3f4f6', padding: '6px 10px', borderRadius: '6px' }}>
                  <strong>Items:</strong> {o.items?.map(it => `${it.item_name} (${it.size}) x ${it.quantity}`).join(', ') || 'N/A'}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', marginBottom: '10px' }}>
                  <span>Total: <strong>₹{o.total}</strong></span>
                  <span>Paid: ₹{o.paid_amount}</span>
                  <span style={{ color: o.balance > 0 ? 'var(--danger)' : 'var(--text-muted)', fontWeight: 'bold' }}>
                    Balance: ₹{o.balance}
                  </span>
                </div>

                {o.cancel_reason && (
                  <div style={{ marginBottom: '10px', fontSize: '0.84rem', color: '#991b1b', background: '#fee2e2', padding: '8px 12px', borderRadius: '6px' }}>
                    <strong>Cancellation Reason:</strong> {o.cancel_reason}
                  </div>
                )}

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    className="btn btn-primary"
                    style={{ flex: 1, height: '38px', minHeight: '38px', fontSize: '0.85rem', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                    onClick={() => handleRevertOrder(o)}
                    disabled={loading}
                  >
                    <RotateCcw size={15} /> Revert / Restore Order
                  </button>

                  <button
                    type="button"
                    onClick={() => api.downloadPdf(o.id, o.bill_no)}
                    className="btn btn-secondary"
                    style={{ height: '38px', minHeight: '38px', fontSize: '0.85rem', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                  >
                    <Download size={14} /> PDF
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ---------------- 3. ITEM-BY-SIZE SALES REPORT ---------------- */}
      {adminTab === 'item_sales' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: '700', margin: 0 }}>Item-by-Size Sales Breakdown</h3>
            <a
              href={api.getItemSalesExcelUrl()}
              download
              className="btn btn-primary"
              style={{ height: '36px', minHeight: '36px', padding: '0 14px', fontSize: '0.85rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              title="Download Item Sales as Excel (without available stock)"
            >
              <Download size={14} /> Export Item Sales (.xlsx)
            </a>
          </div>
          {itemReport.map(item => (
            <div key={item.item_id} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                <strong style={{ fontSize: '1.05rem' }}>{item.item_name}</strong>
                <span style={{ color: 'var(--primary)', fontWeight: 'bold' }}>₹{item.price} each</span>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'center', fontSize: '0.88rem' }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', borderBottom: '1px solid var(--border)' }}>
                      <th style={{ padding: '6px' }}>Size</th>
                      <th style={{ padding: '6px' }}>Available Stock</th>
                      <th style={{ padding: '6px' }}>Units Sold</th>
                      <th style={{ padding: '6px' }}>Revenue (₹)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {item.sizes.map(s => (
                      <tr key={s.size} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '6px', fontWeight: '600' }}>{s.size}</td>
                        <td style={{
                          padding: '6px',
                          color: s.is_low_stock ? 'var(--danger)' : 'var(--text-main)',
                          fontWeight: s.is_low_stock ? 'bold' : 'normal'
                        }}>
                          {s.available_stock} {s.is_low_stock && '(Low)'}
                        </td>
                        <td style={{ padding: '6px', fontWeight: 'bold' }}>{s.sold_qty}</td>
                        <td style={{ padding: '6px', color: 'var(--primary)', fontWeight: 'bold' }}>₹{s.sold_revenue}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ---------------- 4. SELLERS MANAGEMENT ---------------- */}
      {adminTab === 'sellers' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: '700' }}>Authorized Sellers</h3>
            <button
              className="btn btn-primary"
              style={{ height: '38px', minHeight: '38px', padding: '0 14px', fontSize: '0.85rem' }}
              onClick={() => setShowAddSeller(true)}
            >
              + Create Seller
            </button>
          </div>

          {sellersList.map(s => (
            <div key={s.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong style={{ fontSize: '1.02rem', color: 'var(--text-main)' }}>{s.name}</strong>
                <div style={{ fontSize: '0.86rem', color: 'var(--text-muted)', marginTop: '3px' }}>
                  Sales: <strong style={{ color: 'var(--text-main)' }}>₹{s.total_sales || 0}</strong>
                </div>
              </div>

              <div>
                <button
                  className={`btn ${s.is_active ? 'btn-secondary' : 'btn-primary'}`}
                  style={{ height: '36px', minHeight: '36px', fontSize: '0.8rem', padding: '0 12px' }}
                  onClick={() => handleToggleSeller(s.id)}
                >
                  {s.is_active ? 'Deactivate' : 'Activate'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ---------------- 5. STOCK ADJUSTMENT ---------------- */}
      {adminTab === 'stock_mgmt' && (
        <div>
          <h3 style={{ fontSize: '1.15rem', fontWeight: '700', marginBottom: '8px' }}>Common Stock Management</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '14px' }}>
            Adjust common stock pools with an audit reason. Every change writes to the stock movements ledger.
          </p>

          {itemReport.map(item => (
            <div key={item.item_id} className="card">
              <strong style={{ fontSize: '1.05rem' }}>{item.item_name}</strong>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: '8px', marginTop: '10px' }}>
                {item.sizes.map(s => (
                  <div
                    key={s.size}
                    style={{
                      border: '1px solid var(--border)', borderRadius: '8px', padding: '8px', textAlign: 'center',
                      background: s.available_stock <= 5 ? '#fef3c7' : '#fff'
                    }}
                  >
                    <div style={{ fontWeight: '600' }}>Size {s.size}</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 'bold', margin: '4px 0' }}>{s.available_stock}</div>
                    <button
                      className="btn btn-secondary"
                      style={{ height: '30px', minHeight: '30px', fontSize: '0.75rem', width: '100%', padding: 0 }}
                      onClick={() => setAdjustingStockItem({ ...s, item_name: item.item_name })}
                    >
                      Adjust Qty
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ---------------- 6. NAGARS MANAGEMENT ---------------- */}
      {adminTab === 'nagars' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: '700', margin: 0 }}>Official Nagars</h3>
            <a
              href={api.getNagarSalesExcelUrl()}
              download
              className="btn btn-primary"
              style={{ height: '36px', minHeight: '36px', padding: '0 14px', fontSize: '0.85rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              title="Download Nagar-wise sales distribution as Excel"
            >
              <Download size={14} /> Export Nagar Sales (.xlsx)
            </a>
          </div>
          <form onSubmit={handleAddNagar} style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <input
              className="form-control"
              type="text"
              placeholder="Add New Nagar..."
              value={newNagarName}
              onChange={(e) => setNewNagarName(e.target.value)}
              required
            />
            <button type="submit" className="btn btn-primary" style={{ width: '130px' }}>
              + Add
            </button>
          </form>

          {nagarReport.map(n => (
            <div key={n.nagar_id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: '600' }}>{n.nagar_name}</span>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                {n.order_count} orders (₹{n.total_sales})
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ---------------- 7. AUDIT LOG TRAIL ---------------- */}
      {adminTab === 'audit' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: '700' }}>System Audit Trail</h3>
            <button onClick={loadAudit} className="btn btn-secondary" style={{ height: '36px', minHeight: '36px', padding: '0 12px' }}>
              <RefreshCw size={14} /> Refresh
            </button>
          </div>

          {auditLogs.map(a => (
            <div key={a.id} className="card" style={{ fontSize: '0.85rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: '600' }}>
                <span>{a.action} ({a.entity})</span>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{a.created_at}</span>
              </div>
              <div style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
                User: <strong>{a.user_name}</strong> • Details: {a.after}
              </div>
              {a.reason && <div style={{ color: '#ca8a04', marginTop: '2px' }}>Reason: {a.reason}</div>}
            </div>
          ))}
        </div>
      )}

      {/* ---------------- CANCEL ORDER MODAL ---------------- */}
      {cancellingOrder && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.6)', zIndex: 1200,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px'
        }}>
          <div className="card" style={{ maxWidth: '440px', width: '100%' }}>
            <h3 style={{ fontSize: '1.15rem', color: 'var(--danger)', marginBottom: '8px' }}>
              Cancel Order {cancellingOrder.bill_no}
            </h3>
            <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginBottom: '12px' }}>
              Stock will be returned to the pool immediately. If payment was taken, a refund note will be recorded.
            </p>

            <div className="form-group">
              <label className="form-label">Reason for Cancellation (Required)</label>
              <textarea
                className="form-control"
                style={{ height: '80px', padding: '8px' }}
                placeholder="e.g. Buyer changed mind / duplicate order entered"
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <button className="btn btn-secondary" onClick={() => setCancellingOrder(null)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                style={{ backgroundColor: 'var(--danger)' }}
                disabled={!cancelReason.trim() || loading}
                onClick={handleCancelOrder}
              >
                Confirm Cancellation
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------- CREATE SELLER MODAL ---------------- */}
      {showAddSeller && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.6)', zIndex: 1200,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px'
        }}>
          <div className="card" style={{ maxWidth: '440px', width: '100%' }}>
            <h3 style={{ fontSize: '1.15rem', marginBottom: '14px' }}>Create Authorized Seller</h3>
            <form onSubmit={handleCreateSeller}>
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  className="form-control"
                  type="text"
                  placeholder="e.g. Suresh Kumar"
                  value={sellerName}
                  onChange={(e) => setSellerName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Username</label>
                <input
                  className="form-control"
                  type="text"
                  placeholder="e.g. seller2"
                  value={sellerUsername}
                  onChange={(e) => setSellerUsername(e.target.value)}
                  required
                />
              </div>


              <div className="form-group">
                <label className="form-label">Password</label>
                <input
                  className="form-control"
                  type="password"
                  placeholder="••••••••"
                  value={sellerPassword}
                  onChange={(e) => setSellerPassword(e.target.value)}
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowAddSeller(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  Create Seller
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ---------------- ADJUST STOCK MODAL ---------------- */}
      {adjustingStockItem && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.6)', zIndex: 1200,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px'
        }}>
          <div className="card" style={{ maxWidth: '400px', width: '100%' }}>
            <h3 style={{ fontSize: '1.15rem', marginBottom: '8px' }}>
              Adjust Stock: {adjustingStockItem.item_name} (Size {adjustingStockItem.size})
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '14px' }}>
              Current Stock: <strong>{adjustingStockItem.available_stock}</strong>
            </p>

            <div className="form-group">
              <label className="form-label">Quantity Change (Delta)</label>
              <input
                className="form-control"
                type="number"
                placeholder="+10 to add, -5 to reduce"
                value={stockDelta}
                onChange={(e) => setStockDelta(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Reason</label>
              <input
                className="form-control"
                type="text"
                placeholder="e.g. New stock consignment received"
                value={stockReason}
                onChange={(e) => setStockReason(e.target.value)}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <button className="btn btn-secondary" onClick={() => setAdjustingStockItem(null)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={handleStockUpdate}>
                Save Stock
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
