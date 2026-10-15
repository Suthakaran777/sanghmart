import React, { useState, useEffect, useRef } from 'react';
import { api } from './api';
import AdminDashboard from './AdminDashboard';
import BhagwaDhwaj from './BhagwaDhwaj';
import {
  ShoppingBag, Plus, Minus, Trash2, Send, CheckCircle,
  RefreshCw, LogOut, ArrowLeft, AlertTriangle, FileText,
  DollarSign, QrCode, UploadCloud, Download, Camera, Image, ShieldCheck,
  LayoutDashboard, Banknote, Clock, XCircle
} from 'lucide-react';

export default function App() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [tab, setTab] = useState('new_order'); // new_order, pending, history, stock
  
  // Auth state
  const [usernameInput, setUsernameInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  const [authError, setAuthError] = useState('');
  
  // Catalogue state
  const [catalogue, setCatalogue] = useState({ items: [], nagars: [] });
  const [loading, setLoading] = useState(false);

  // New Order state
  const [selectedItem, setSelectedItem] = useState(null);
  const [selectedSize, setSelectedSize] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [cart, setCart] = useState([]);
  
  // Buyer form
  const [buyerName, setBuyerName] = useState('');
  const [buyerPhone, setBuyerPhone] = useState('');
  const [buyerNagarId, setBuyerNagarId] = useState('');
  const [pendingAlert, setPendingAlert] = useState(null);

  // Payment choice
  const [payMode, setPayMode] = useState('now_cash'); // now_cash, now_upi, pending
  const [advanceAmount, setAdvanceAmount] = useState(0);
  const [completedOrder, setCompletedOrder] = useState(null);

  // UPI Flow Modal State (Step 1: Show QR -> Step 2: Camera / Upload Proof -> Step 3: Seller verification -> Approve)
  const [showUpiModal, setShowUpiModal] = useState(false);
  const [upiStep, setUpiStep] = useState(1); // 1 = Show QR, 2 = Capture/Upload Proof & Verify
  const [upiProofPreview, setUpiProofPreview] = useState(null);
  const [upiProofFileId, setUpiProofFileId] = useState(null);
  const [upiUtr, setUpiUtr] = useState('');
  const [upiSellerVerified, setUpiSellerVerified] = useState(false);
  const [upiTargetOrder, setUpiTargetOrder] = useState(null); // if collecting pending payment

  // Camera capture modal state
  const [showCameraStream, setShowCameraStream] = useState(false);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  // Cash Confirmation Modal
  const [showCashConfirmModal, setShowCashConfirmModal] = useState(false);
  const [cashConfirmed, setCashConfirmed] = useState(false);

  // Collect Payment Modal state (for pending orders)
  const [activePaymentOrder, setActivePaymentOrder] = useState(null);
  const [collectAmount, setCollectAmount] = useState(0);
  const [collectMethod, setCollectMethod] = useState('cash'); // cash, upi

  // My Orders list
  const [myOrders, setMyOrders] = useState([]);
  const [historyFilter, setHistoryFilter] = useState('all'); // all, active, cancelled

  // Check login on mount
  useEffect(() => {
    if (token) {
      api.getMe()
        .then((u) => {
          setUser(u);
          if (u.role === 'admin') setTab('admin_panel');
          loadCatalogue();
        })
        .catch(() => {
          handleLogout();
        });
    }
  }, [token]);

  // Clean up camera stream on unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthError('');
    try {
      const data = await api.postLogin(usernameInput, passwordInput);
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
      setUser({ name: data.name, role: data.role, username: data.username });
      if (data.role === 'admin') {
        setTab('admin_panel');
      } else {
        setTab('new_order');
      }
      loadCatalogue();
    } catch (err) {
      setAuthError(err.message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken('');
    setUser(null);
  };

  const loadCatalogue = async () => {
    try {
      setLoading(true);
      const data = await api.getCatalogue();
      setCatalogue(data);
      if (data.items.length > 0 && !selectedItem) {
        setSelectedItem(data.items[0]);
        if (data.items[0].sizes.length > 0) {
          setSelectedSize(data.items[0].sizes[0].size);
        }
      }
      // Keep buyerNagarId default to empty string so it shows "Select a Nagar"
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handlePhoneBlur = async () => {
    if (buyerPhone.length >= 10) {
      try {
        const buyer = await api.getBuyerByPhone(buyerPhone);
        if (buyer) {
          setBuyerName(buyer.name);
          if (buyer.nagar_id) setBuyerNagarId(buyer.nagar_id);
          if (buyer.pending_balance > 0) {
            setPendingAlert(`⚠️ Buyer has an unpaid pending balance of ₹${buyer.pending_balance}!`);
          } else {
            setPendingAlert(null);
          }
        }
      } catch (e) {
        console.error(e);
      }
    }
  };

  const addToCart = () => {
    if (!selectedItem || !selectedSize) return;
    const sizeObj = selectedItem.sizes.find(s => s.size === selectedSize);
    if (!sizeObj || sizeObj.stock_qty <= 0) {
      alert("This size is currently out of stock!");
      return;
    }

    const existingIndex = cart.findIndex(c => c.itemId === selectedItem.id && c.size === selectedSize);
    if (existingIndex >= 0) {
      const updated = [...cart];
      if (updated[existingIndex].quantity + quantity > sizeObj.stock_qty) {
        alert(`Cannot add more than available common stock (${sizeObj.stock_qty})!`);
        return;
      }
      updated[existingIndex].quantity += quantity;
      setCart(updated);
    } else {
      if (quantity > sizeObj.stock_qty) {
        alert(`Cannot add more than available common stock (${sizeObj.stock_qty})!`);
        return;
      }
      setCart([
        ...cart,
        {
          itemId: selectedItem.id,
          itemName: selectedItem.name,
          size: selectedSize,
          unitPrice: selectedItem.price,
          quantity: quantity
        }
      ]);
    }
  };

  const removeFromCart = (index) => {
    setCart(cart.filter((_, i) => i !== index));
  };

  const cartEstimatedTotal = cart.reduce((acc, item) => acc + item.unitPrice * item.quantity, 0);

  // ---------------- CAMERA UTILITIES ----------------
  const startCamera = async () => {
    setShowCameraStream(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } }
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
    } catch (err) {
      console.warn("Direct camera access failed or unavailable, fallback to file capture", err);
      setShowCameraStream(false);
      // Fallback: trigger native file camera input
      document.getElementById('nativeCameraInput')?.click();
    }
  };

  const capturePhoto = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
    setUpiProofPreview(dataUrl);

    // Convert dataUrl to blob and upload
    canvas.toBlob(async (blob) => {
      const file = new File([blob], `proof_${Date.now()}.jpg`, { type: 'image/jpeg' });
      try {
        setLoading(true);
        const res = await api.uploadProof(file);
        setUpiProofFileId(res.file_id);
      } catch (err) {
        alert(`Upload failed: ${err.message}`);
      } finally {
        setLoading(false);
      }
    }, 'image/jpeg', 0.85);

    stopCamera();
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setShowCameraStream(false);
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Show preview immediately
    const reader = new FileReader();
    reader.onload = () => setUpiProofPreview(reader.result);
    reader.readAsDataURL(file);

    try {
      setLoading(true);
      const res = await api.uploadProof(file);
      setUpiProofFileId(res.file_id);
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // ---------------- ORDER CREATION & VALIDATION ----------------
  const validateOrderInputs = () => {
    if (cart.length === 0) {
      alert("Cart is empty! Add items first.");
      return false;
    }
    if (!buyerName.trim()) {
      alert("Please enter Buyer Name.");
      return false;
    }
    if (!buyerPhone.trim() || buyerPhone.length < 10) {
      alert("Please enter a valid 10-digit Mobile Number.");
      return false;
    }
    if (!buyerNagarId) {
      alert("Please select a Nagar from the dropdown.");
      return false;
    }
    return true;
  };

  const handleInitiatePayment = () => {
    if (!validateOrderInputs()) return;

    if (payMode === 'now_cash') {
      setCashConfirmed(false);
      setShowCashConfirmModal(true);
    } else if (payMode === 'now_upi') {
      setUpiTargetOrder(null);
      setUpiStep(1); // Step 1: Show QR code first
      setUpiProofPreview(null);
      setUpiProofFileId(null);
      setUpiUtr('');
      setUpiSellerVerified(false);
      setShowUpiModal(true);
    } else {
      // Pending order
      finalizeOrder(null, null);
    }
  };

  const finalizeOrder = async (utr = null, proofId = null) => {
    const idempotencyKey = `ord-${user.username}-${Date.now()}`;
    const payload = {
      buyer_name: buyerName.trim(),
      buyer_phone: buyerPhone.trim(),
      nagar_id: Number(buyerNagarId),
      items: cart.map(c => ({
        item_id: c.itemId,
        size: c.size,
        quantity: c.quantity
      })),
      pay_now: payMode === 'now_cash' || payMode === 'now_upi',
      payment_method: payMode === 'now_cash' ? 'cash' : (payMode === 'now_upi' ? 'upi' : null),
      advance_amount: payMode === 'pending' ? Number(advanceAmount) : 0,
      utr: utr,
      screenshot_file_id: proofId
    };

    try {
      setLoading(true);
      const orderRes = await api.createOrder(payload, idempotencyKey);
      setCompletedOrder(orderRes);
      // Reset form
      setCart([]);
      setBuyerName('');
      setBuyerPhone('');
      setPendingAlert(null);
      setShowUpiModal(false);
      setShowCashConfirmModal(false);
      loadCatalogue();
    } catch (err) {
      alert(`Order Failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Collect payment on pending orders
  const handlePendingUpiCollection = (order) => {
    setActivePaymentOrder(order);
    setUpiTargetOrder(order);
    setCollectAmount(order.balance);
    setUpiStep(1);
    setUpiProofPreview(null);
    setUpiProofFileId(null);
    setUpiUtr('');
    setUpiSellerVerified(false);
    setShowUpiModal(true);
  };

  const submitPendingCollectedPayment = async () => {
    if (!upiTargetOrder) return;
    try {
      setLoading(true);
      await api.collectPayment(
        upiTargetOrder.id,
        Number(collectAmount),
        'upi',
        upiUtr.trim() || null,
        upiProofFileId,
        `Collected via UPI with camera proof`
      );
      alert("Payment recorded successfully!");
      setShowUpiModal(false);
      setActivePaymentOrder(null);
      loadMyOrders();
    } catch (err) {
      alert(`Payment failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handlePendingCashCollection = async (order) => {
    const confirmed = window.confirm(`Confirm receiving ₹${order.balance} in CASH from ${order.buyer_name}?`);
    if (!confirmed) return;
    try {
      setLoading(true);
      await api.collectPayment(
        order.id,
        Number(order.balance),
        'cash',
        null,
        null,
        `Collected via Cash`
      );
      alert("Cash payment recorded successfully!");
      loadMyOrders();
    } catch (err) {
      alert(`Payment failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const loadMyOrders = async () => {
    try {
      setLoading(true);
      const orders = await api.getMyOrders();
      setMyOrders(orders);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // ---------------- LOGIN VIEW ----------------
  if (!user) {
    return (
      <div className="app-container" style={{ justifyContent: 'center', padding: '24px' }}>
        <div className="card" style={{ textAlign: 'center', padding: '32px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '18px' }}>
            <div style={{
              width: '124px',
              height: '124px',
              borderRadius: '50%',
              backgroundColor: '#fff7ed',
              border: '1.5px solid #ffedd5',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 10px 28px rgba(234, 88, 12, 0.12)'
            }}>
              <BhagwaDhwaj size={96} animated={true} />
            </div>
          </div>
          <h2 style={{ fontSize: '1.75rem', color: 'var(--primary)', fontWeight: '800', marginBottom: '4px' }}>Sangh Mart</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem', marginBottom: '24px' }}>
            Vijayadashami Uniform Sales Portal
          </p>

          {authError && <div className="banner banner-error">{authError}</div>}

          <form onSubmit={handleLogin}>
            <div className="form-group" style={{ textAlign: 'left' }}>
              <label className="form-label">Username</label>
              <input
                className="form-control"
                type="text"
                placeholder="seller1 or admin"
                value={usernameInput}
                onChange={(e) => setUsernameInput(e.target.value)}
                required
              />
            </div>

            <div className="form-group" style={{ textAlign: 'left' }}>
              <label className="form-label">Password</label>
              <input
                className="form-control"
                type="password"
                placeholder="••••••••"
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                required
              />
            </div>

            <button type="submit" className="btn btn-primary" style={{ marginTop: '8px' }}>
              Sign In
            </button>
          </form>
        </div>
      </div>
    );
  }

  // ---------------- BILL CREATED VIEW ----------------
  if (completedOrder) {
    const pdfUrl = api.getPdfUrl(completedOrder.id);
    return (
      <div className="app-container">
        <header className="app-header">
          <div className="brand-title">📄 Bill Details</div>
          <button
            className="btn btn-secondary"
            style={{ minHeight: '36px', minWidth: '36px', padding: '6px' }}
            onClick={() => setCompletedOrder(null)}
          >
            <ArrowLeft size={18} />
          </button>
        </header>

        <div style={{ padding: '16px' }}>
          <div className="card" style={{ textAlign: 'center', borderTop: '4px solid var(--primary)' }}>
            <h3 style={{ color: 'var(--primary)', marginBottom: '4px' }}>{completedOrder.bill_no}</h3>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              Buyer: <strong>{completedOrder.buyer_name}</strong> ({completedOrder.buyer_phone})
            </div>
            
            <div style={{ margin: '16px 0', padding: '12px', background: '#f8fafc', borderRadius: '8px', textAlign: 'left' }}>
              {completedOrder.items.map(it => (
                <div key={it.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span>{it.item_name} (Size {it.size}) × {it.quantity}</span>
                  <span style={{ fontWeight: 'bold' }}>₹{it.line_total}</span>
                </div>
              ))}
              <div style={{ borderTop: '1px dashed #cbd5e1', marginTop: '8px', paddingTop: '8px', display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 'bold' }}>Total:</span>
                <span style={{ fontWeight: 'bold', fontSize: '1.1rem', color: 'var(--primary)' }}>₹{completedOrder.total}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px', fontSize: '0.9rem' }}>
                <span>Paid so far: ₹{completedOrder.paid_amount}</span>
                <span style={{ color: completedOrder.balance > 0 ? 'var(--danger)' : 'var(--success)', fontWeight: 'bold' }}>
                  Balance due: ₹{completedOrder.balance}
                </span>
              </div>
              <div style={{ marginTop: '6px', textAlign: 'right' }}>
                <span className={`chip chip-${completedOrder.payment_status.toLowerCase()}`}>
                  {completedOrder.payment_status}
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <a
                href={completedOrder.whatsapp_url}
                target="_blank"
                rel="noreferrer"
                className="btn btn-whatsapp"
                style={{ textDecoration: 'none', width: '100%', height: '44px' }}
              >
                <Send size={18} /> Send on WhatsApp
              </a>

              <button
                type="button"
                onClick={() => api.downloadPdf(completedOrder.id, completedOrder.bill_no)}
                className="btn btn-secondary"
                style={{ width: '100%', height: '44px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
              >
                <Download size={18} /> Download PDF Bill
              </button>

              <button
                className="btn btn-outline"
                style={{ width: '100%', marginTop: '6px' }}
                onClick={() => setCompletedOrder(null)}
              >
                + New Order
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---------------- CAMERA STREAM MODAL ----------------
  const renderCameraModal = () => {
    if (!showCameraStream) return null;
    return (
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: '#000', zIndex: 1100,
        display: 'flex', flexDirection: 'column', justifyContent: 'space-between', padding: '16px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#fff' }}>
          <span style={{ fontWeight: 'bold' }}>Capture Buyer's Paid Screen</span>
          <button
            onClick={stopCamera}
            style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '1.6rem', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
          <video
            ref={videoRef}
            playsInline
            muted
            style={{ width: '100%', maxHeight: '75vh', objectFit: 'contain', borderRadius: '12px' }}
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', paddingBottom: '20px' }}>
          <button
            onClick={capturePhoto}
            style={{
              width: '74px', height: '74px', borderRadius: '50%',
              backgroundColor: '#fff', border: '4px solid #ea580c',
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}
          >
            <Camera size={34} color="#ea580c" />
          </button>
        </div>
      </div>
    );
  };

  // ---------------- CASH CONFIRMATION MODAL ----------------
  const renderCashConfirmModal = () => {
    if (!showCashConfirmModal) return null;
    return (
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.6)', zIndex: 1000,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px'
      }}>
        <div className="card" style={{ maxWidth: '420px', width: '100%' }}>
          <h3 style={{ fontSize: '1.2rem', marginBottom: '12px', color: 'var(--success)' }}>💵 Verify Cash Payment</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', marginBottom: '16px' }}>
            Order Amount: <strong style={{ fontSize: '1.2rem', color: 'var(--text-main)' }}>₹{cartEstimatedTotal}</strong>
          </p>

          <div style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input
              type="checkbox"
              id="cashCheck"
              checked={cashConfirmed}
              onChange={(e) => setCashConfirmed(e.target.checked)}
              style={{ width: '22px', height: '22px', cursor: 'pointer' }}
            />
            <label htmlFor="cashCheck" style={{ fontSize: '0.92rem', fontWeight: 'bold', cursor: 'pointer' }}>
              I received ₹{cartEstimatedTotal} in cash and verified it.
            </label>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <button className="btn btn-secondary" onClick={() => setShowCashConfirmModal(false)}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              disabled={!cashConfirmed || loading}
              onClick={() => finalizeOrder(null, null)}
            >
              {loading ? 'Creating...' : 'Approve & Create Bill'}
            </button>
          </div>
        </div>
      </div>
    );
  };

  // ---------------- TWO-STEP UPI MODAL (SHOW QR -> CAMERA/UPLOAD PROOF -> APPROVE) ----------------
  const renderUpiModal = () => {
    if (!showUpiModal) return null;
    const amountToPay = upiTargetOrder ? collectAmount : cartEstimatedTotal;

    return (
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.65)', zIndex: 1000,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px'
      }}>
        <div className="card" style={{ maxWidth: '460px', width: '100%', maxHeight: '92vh', overflowY: 'auto' }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div>
              <h3 style={{ fontSize: '1.15rem' }}>
                {upiStep === 1 ? 'Step 1: Scan Organizer QR' : 'Step 2: Buyer Proof & Verification'}
              </h3>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {upiStep === 1 ? 'Show this QR code to the buyer to pay' : 'Capture screen or upload screenshot proof'}
              </div>
            </div>
            <button
              onClick={() => setShowUpiModal(false)}
              style={{ background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer' }}
            >
              ×
            </button>
          </div>

          {/* STEP 1: SHOW ORGANIZER QR CODE FIRST */}
          {upiStep === 1 && (
            <div style={{ textAlign: 'center' }}>
              <div style={{
                background: '#fff', border: '2px solid #e2e8f0', borderRadius: '12px',
                padding: '12px', display: 'inline-block', boxShadow: '0 4px 12px rgba(0,0,0,0.06)'
              }}>
                <img
                  src="/organizer_qr.jpg"
                  alt="Organizer Google Pay QR"
                  style={{ width: '240px', height: 'auto', maxHeight: '310px', borderRadius: '8px', objectFit: 'contain' }}
                />
              </div>

              <div style={{ marginTop: '12px' }}>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>UPI ID</div>
                <div style={{ fontSize: '1.05rem', fontWeight: 'bold', color: '#1e293b' }}>
                  asuthakaran2006@oksbi
                </div>
              </div>

              <div style={{ marginTop: '10px', padding: '10px', background: '#eff6ff', borderRadius: '8px' }}>
                <span style={{ fontSize: '0.85rem', color: '#1e40af' }}>Amount to Pay:</span>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#1d4ed8' }}>₹{amountToPay}</div>
              </div>

              <button
                className="btn btn-primary"
                style={{ marginTop: '16px' }}
                onClick={() => setUpiStep(2)}
              >
                Buyer Has Paid 👉 Proceed to Verify
              </button>
            </div>
          )}

          {/* STEP 2: CAMERA CAPTURE / UPLOAD SCREENSHOT & APPROVE */}
          {upiStep === 2 && (
            <div>
              <div style={{ padding: '10px', background: '#f8fafc', borderRadius: '8px', marginBottom: '14px', fontSize: '0.9rem' }}>
                Amount Paid: <strong style={{ color: 'var(--primary)' }}>₹{amountToPay}</strong>
              </div>

              {/* Camera or Upload Screenshot Options */}
              <div style={{ marginBottom: '14px' }}>
                <label className="form-label">Buyer's Paid Screenshot Proof</label>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '10px' }}>
                  {/* Button 1: Open Camera directly */}
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={startCamera}
                    style={{ flexDirection: 'column', height: '60px', fontSize: '0.82rem', gap: '4px' }}
                  >
                    <Camera size={20} color="var(--primary)" />
                    <span>Open Camera</span>
                  </button>

                  {/* Button 2: Upload Screenshot from Gallery */}
                  <label
                    className="btn btn-secondary"
                    style={{
                      flexDirection: 'column', height: '60px', fontSize: '0.82rem', gap: '4px',
                      cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}
                  >
                    <Image size={20} color="#2563eb" />
                    <span>Upload Screenshot</span>
                    <input
                      type="file"
                      accept="image/*"
                      style={{ display: 'none' }}
                      onChange={handleFileUpload}
                    />
                  </label>
                </div>

                {/* Hidden native camera input for older browser fallbacks */}
                <input
                  id="nativeCameraInput"
                  type="file"
                  accept="image/*"
                  capture="environment"
                  style={{ display: 'none' }}
                  onChange={handleFileUpload}
                />

                {/* Proof preview thumbnail */}
                {upiProofPreview && (
                  <div style={{ textAlign: 'center', padding: '8px', background: '#f1f5f9', borderRadius: '8px' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--success)', fontWeight: 'bold', marginBottom: '4px' }}>
                      ✓ Proof Captured
                    </div>
                    <img
                      src={upiProofPreview}
                      alt="Proof Preview"
                      style={{ maxHeight: '160px', maxWidth: '100%', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                    />
                  </div>
                )}
              </div>

              {/* Optional UTR */}
              <div className="form-group">
                <label className="form-label">Optional 12-digit UTR Number</label>
                <input
                  className="form-control"
                  type="text"
                  placeholder="e.g. 428900112233"
                  maxLength={12}
                  value={upiUtr}
                  onChange={(e) => setUpiUtr(e.target.value)}
                />
              </div>

              {/* Seller Verification Checkbox */}
              <div style={{ marginBottom: '18px', padding: '10px', background: '#fefce8', borderRadius: '8px', border: '1px solid #fef08a' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <input
                    type="checkbox"
                    id="upiSellerCheck"
                    checked={upiSellerVerified}
                    onChange={(e) => setUpiSellerVerified(e.target.checked)}
                    style={{ width: '22px', height: '22px', cursor: 'pointer' }}
                  />
                  <label htmlFor="upiSellerCheck" style={{ fontSize: '0.88rem', fontWeight: 'bold', cursor: 'pointer' }}>
                    I checked my Google Pay / Bank app and verified that ₹{amountToPay} was credited.
                  </label>
                </div>
              </div>

              {/* Action buttons */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '8px' }}>
                <button className="btn btn-secondary" onClick={() => setUpiStep(1)}>
                  ← Back to QR
                </button>
                <button
                  className="btn btn-primary"
                  disabled={!upiSellerVerified || loading}
                  onClick={() => {
                    if (upiTargetOrder) {
                      submitPendingCollectedPayment();
                    } else {
                      finalizeOrder(upiUtr.trim() || null, upiProofFileId);
                    }
                  }}
                >
                  {loading ? 'Processing...' : 'Approve & Release Bill'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  // ---------------- MAIN INTERFACE ----------------
  const pendingOrders = myOrders.filter(o => o.balance > 0 && o.order_status === 'Active');

  return (
    <div className={`app-container ${user.role === 'admin' ? 'admin-mode' : ''}`}>
      {renderCameraModal()}
      {renderCashConfirmModal()}
      {renderUpiModal()}

      {/* Header */}
      <header className="app-header">
        <div className="brand-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <BhagwaDhwaj size={24} />
          <span>Sangh Mart</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.85rem', background: 'rgba(255,255,255,0.2)', padding: '4px 8px', borderRadius: '4px' }}>
            {user.name} ({user.role})
          </span>
          <button
            onClick={handleLogout}
            style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', padding: '4px' }}
            title="Logout"
          >
            <LogOut size={20} />
          </button>
        </div>
      </header>

      {/* Navigation Tabs */}
      <div className="main-nav-bar" style={{ display: 'flex', borderBottom: '1px solid var(--border)', background: '#fff' }}>
        {user.role === 'admin' && (
          <button
            onClick={() => setTab('admin_panel')}
            className="nav-tab-btn"
            style={{
              flex: 1,
              borderRadius: 0,
              borderBottom: tab === 'admin_panel' ? '3px solid var(--primary)' : 'none',
              color: tab === 'admin_panel' ? 'var(--primary)' : 'var(--text-muted)',
              backgroundColor: 'transparent',
              fontWeight: 'bold',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px'
            }}
          >
            <LayoutDashboard size={15} />
            <span>Admin Panel</span>
          </button>
        )}
        <button
          onClick={() => setTab('new_order')}
          className="nav-tab-btn"
          style={{
            flex: 1,
            borderRadius: 0,
            borderBottom: tab === 'new_order' ? '3px solid var(--primary)' : 'none',
            color: tab === 'new_order' ? 'var(--primary)' : 'var(--text-muted)',
            backgroundColor: 'transparent',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px'
          }}
        >
          <ShoppingBag size={15} />
          <span>New Order</span>
        </button>
        <button
          onClick={() => { setTab('pending'); loadMyOrders(); }}
          className="nav-tab-btn"
          style={{
            flex: 1,
            borderRadius: 0,
            borderBottom: tab === 'pending' ? '3px solid var(--primary)' : 'none',
            color: tab === 'pending' ? 'var(--primary)' : 'var(--text-muted)',
            backgroundColor: 'transparent',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px'
          }}
        >
          <Clock size={15} />
          <span>Pending ({pendingOrders.length})</span>
        </button>
        <button
          onClick={() => { setTab('history'); loadMyOrders(); }}
          className="nav-tab-btn"
          style={{
            flex: 1,
            borderRadius: 0,
            borderBottom: tab === 'history' ? '3px solid var(--primary)' : 'none',
            color: tab === 'history' ? 'var(--primary)' : 'var(--text-muted)',
            backgroundColor: 'transparent',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px'
          }}
        >
          <FileText size={15} />
          <span>History</span>
        </button>
      </div>

      {/* Body Area */}
      {tab === 'admin_panel' && user.role === 'admin' ? (
        <AdminDashboard user={user} />
      ) : (
      <div style={{ padding: '16px', flex: 1 }}>
        {/* NEW ORDER */}
        {tab === 'new_order' && (
          <div>
            <div className="card">
              <h3 style={{ fontSize: '1.05rem', marginBottom: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Uniform Items</span>
                <button
                  onClick={loadCatalogue}
                  style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                >
                  <RefreshCw size={16} />
                </button>
              </h3>

              {/* Items grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '12px' }}>
                {catalogue.items.map(item => (
                  <button
                    key={item.id}
                    className={`item-select-btn ${selectedItem?.id === item.id ? 'selected' : ''}`}
                    onClick={() => {
                      setSelectedItem(item);
                      if (item.sizes.length > 0) setSelectedSize(item.sizes[0].size);
                      setQuantity(1); // Reset quantity to default 1 when switching item
                    }}
                    style={{
                      height: '54px',
                      borderRadius: '8px',
                      border: selectedItem?.id === item.id ? '2px solid #9a3412' : '1px solid var(--border)',
                      backgroundColor: selectedItem?.id === item.id ? '#d9531e' : '#fff',
                      color: selectedItem?.id === item.id ? '#ffffff' : 'var(--text-main)',
                      flexDirection: 'column',
                      gap: '2px',
                      fontSize: '0.85rem'
                    }}
                  >
                    <strong style={{ color: selectedItem?.id === item.id ? '#ffffff' : 'inherit' }}>{item.name}</strong>
                    <span style={{ fontSize: '0.78rem', color: selectedItem?.id === item.id ? '#ffedd5' : 'var(--text-muted)' }}>₹{item.price}</span>
                  </button>
                ))}
              </div>

              {/* Sizes */}
              {selectedItem && (
                <div style={{ marginBottom: '12px' }}>
                  <label className="form-label">Available Sizes (Common Pool)</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {selectedItem.sizes.map(s => {
                      const isOutOfStock = s.stock_qty <= 0;
                      return (
                        <button
                          key={s.id}
                          className={`size-select-btn ${selectedSize === s.size ? 'selected' : ''}`}
                          disabled={isOutOfStock}
                          onClick={() => setSelectedSize(s.size)}
                          style={{
                            minWidth: '56px',
                            height: '48px',
                            borderRadius: '8px',
                            border: selectedSize === s.size ? '2px solid #9a3412' : '1px solid var(--border)',
                            backgroundColor: isOutOfStock ? '#f1f5f9' : (selectedSize === s.size ? '#d9531e' : '#fff'),
                            color: isOutOfStock ? '#94a3b8' : (selectedSize === s.size ? '#ffffff' : 'var(--text-main)'),
                            opacity: isOutOfStock ? 0.6 : 1,
                            flexDirection: 'column',
                            padding: '4px'
                          }}
                        >
                          <span style={{ fontWeight: 'bold', color: selectedSize === s.size ? '#ffffff' : 'inherit' }}>{s.size}</span>
                          <span style={{ fontSize: '0.7rem', color: selectedSize === s.size ? '#ffedd5' : 'inherit' }}>{isOutOfStock ? '0' : `${s.stock_qty} left`}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Quantity Stepper */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <button className="stepper-btn" onClick={() => setQuantity(Math.max(1, quantity - 1))}>-</button>
                  <span style={{ fontSize: '1.2rem', fontWeight: 'bold', width: '36px', textAlign: 'center' }}>{quantity}</span>
                  <button className="stepper-btn" onClick={() => setQuantity(quantity + 1)}>+</button>
                </div>
                <button className="btn btn-add-to-cart" style={{ flex: 1 }} onClick={addToCart}>
                  <ShoppingBag size={18} /> Add to Cart
                </button>
              </div>
            </div>

            {/* Cart summary */}
            {cart.length > 0 && (
              <div className="card" style={{ borderColor: 'var(--primary)' }}>
                <h3 style={{ fontSize: '1.05rem', marginBottom: '10px' }}>Cart ({cart.length} items)</h3>
                {cart.map((c, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid #f1f5f9' }}>
                    <div>
                      <strong>{c.itemName}</strong> (Size {c.size}) × {c.quantity}
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>₹{c.unitPrice} each</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontWeight: 'bold' }}>₹{c.unitPrice * c.quantity}</span>
                      <button onClick={() => removeFromCart(i)} className="trash-btn" style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer' }}>
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))}
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '12px', fontSize: '1.1rem', fontWeight: 'bold' }}>
                  <span>Estimated Total:</span>
                  <span style={{ color: 'var(--primary)' }}>₹{cartEstimatedTotal}</span>
                </div>
              </div>
            )}

            {/* Buyer Details */}
            <div className="card">
              <h3 style={{ fontSize: '1.05rem', marginBottom: '12px' }}>Buyer Information</h3>
              {pendingAlert && (
                <div className="banner banner-warning" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <AlertTriangle size={20} />
                  <span>{pendingAlert}</span>
                </div>
              )}
              <div className="form-group">
                <label className="form-label">WhatsApp Mobile Number</label>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <span style={{ padding: '0 12px', background: '#f1f5f9', height: '48px', display: 'flex', alignItems: 'center', border: '1.5px solid var(--border)', borderRight: 'none', borderRadius: '8px 0 0 8px', fontWeight: 'bold' }}>
                    +91
                  </span>
                  <input
                    className="form-control"
                    style={{ borderRadius: '0 8px 8px 0' }}
                    type="tel"
                    placeholder="9876543210"
                    maxLength={10}
                    value={buyerPhone}
                    onChange={(e) => setBuyerPhone(e.target.value)}
                    onBlur={handlePhoneBlur}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Buyer Full Name</label>
                <input
                  className="form-control"
                  type="text"
                  placeholder="e.g. Ramesh Patel"
                  value={buyerName}
                  onChange={(e) => setBuyerName(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Select Nagar</label>
                <select
                  className="form-control"
                  value={buyerNagarId}
                  onChange={(e) => setBuyerNagarId(e.target.value)}
                >
                  <option value="">-- Select a Nagar --</option>
                  {catalogue.nagars.map(n => (
                    <option key={n.id} value={n.id}>{n.name}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Payment Mode Selection */}
            <div className="card">
              <h3 style={{ fontSize: '1.05rem', marginBottom: '12px' }}>Payment Option</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '14px' }}>
                <button
                  onClick={() => setPayMode('now_cash')}
                  className={`pay-mode-btn pay-mode-btn-cash ${payMode === 'now_cash' ? 'selected' : ''}`}
                  style={{
                    border: payMode === 'now_cash' ? '2px solid #14532d' : '1px solid var(--border)',
                    backgroundColor: payMode === 'now_cash' ? '#15803d' : '#fff',
                    color: payMode === 'now_cash' ? '#ffffff' : 'var(--text-main)',
                    flexDirection: 'column',
                    gap: '4px',
                    fontSize: '0.85rem'
                  }}
                >
                  <Banknote size={18} color={payMode === 'now_cash' ? '#ffffff' : 'var(--success)'} />
                  <span style={{ color: payMode === 'now_cash' ? '#ffffff' : 'inherit' }}>Cash Now</span>
                </button>
                <button
                  onClick={() => setPayMode('now_upi')}
                  className={`pay-mode-btn pay-mode-btn-upi ${payMode === 'now_upi' ? 'selected' : ''}`}
                  style={{
                    border: payMode === 'now_upi' ? '2px solid #1e3a8a' : '1px solid var(--border)',
                    backgroundColor: payMode === 'now_upi' ? '#1d4ed8' : '#fff',
                    color: payMode === 'now_upi' ? '#ffffff' : 'var(--text-main)',
                    flexDirection: 'column',
                    gap: '4px',
                    fontSize: '0.85rem'
                  }}
                >
                  <QrCode size={18} color={payMode === 'now_upi' ? '#ffffff' : '#2563eb'} />
                  <span style={{ color: payMode === 'now_upi' ? '#ffffff' : 'inherit' }}>UPI QR</span>
                </button>
                <button
                  onClick={() => setPayMode('pending')}
                  className={`pay-mode-btn pay-mode-btn-pending ${payMode === 'pending' ? 'selected' : ''}`}
                  style={{
                    border: payMode === 'pending' ? '2px solid #78350f' : '1px solid var(--border)',
                    backgroundColor: payMode === 'pending' ? '#b45309' : '#fff',
                    color: payMode === 'pending' ? '#ffffff' : 'var(--text-main)',
                    flexDirection: 'column',
                    gap: '4px',
                    fontSize: '0.85rem'
                  }}
                >
                  <Clock size={18} color={payMode === 'pending' ? '#ffffff' : '#ca8a04'} />
                  <span style={{ color: payMode === 'pending' ? '#ffffff' : 'inherit' }}>Pending List</span>
                </button>
              </div>

              {payMode === 'pending' && (
                <div className="form-group">
                  <label className="form-label">Advance Paid Now (₹)</label>
                  <input
                    className="form-control"
                    type="number"
                    min="0"
                    max={cartEstimatedTotal}
                    value={advanceAmount}
                    onChange={(e) => setAdvanceAmount(e.target.value)}
                  />
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Remaining balance: ₹{Math.max(0, cartEstimatedTotal - Number(advanceAmount))}
                  </div>
                </div>
              )}

              <button
                className="btn btn-primary"
                onClick={handleInitiatePayment}
                disabled={loading || cart.length === 0}
              >
                {loading ? 'Processing...' : (
                  payMode === 'now_upi'
                    ? `Show UPI QR & Pay (₹${cartEstimatedTotal})`
                    : (payMode === 'pending' ? 'Save to Pending List' : `Confirm Cash Order (₹${cartEstimatedTotal})`)
                )}
              </button>
            </div>
          </div>
        )}

        {/* PENDING ORDERS */}
        {tab === 'pending' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ fontSize: '1.1rem' }}>Pending Orders</h3>
              <button onClick={loadMyOrders} className="btn btn-secondary" style={{ minHeight: '36px', padding: '6px 12px' }}>
                <RefreshCw size={16} /> Refresh
              </button>
            </div>

            {pendingOrders.length === 0 ? (
              <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                🎉 No pending orders! All your orders are fully settled.
              </div>
            ) : (
              pendingOrders.map(o => (
                <div key={o.id} className="card" style={{ borderLeft: '4px solid var(--warning)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 'bold' }}>{o.bill_no}</span>
                    <span className="chip chip-partial">₹{o.balance} Due</span>
                  </div>
                  <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', margin: '6px 0' }}>
                    👤 {o.buyer_name} ({o.buyer_phone}) • {o.nagar_name || 'N/A'}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem' }}>
                    <span>Total: ₹{o.total}</span>
                    <span>Paid: ₹{o.paid_amount}</span>
                  </div>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: o.whatsapp_url ? '1fr 1fr 1fr' : '1fr 1fr', gap: '8px', marginTop: '12px' }}>
                    <button
                      className="btn btn-success"
                      style={{ height: '40px', minHeight: '40px', fontSize: '0.82rem', padding: '0 6px' }}
                      onClick={() => handlePendingCashCollection(o)}
                    >
                      <Banknote size={15} /> Collect Cash
                    </button>
                    <button
                      className="btn btn-primary"
                      style={{ height: '40px', minHeight: '40px', fontSize: '0.82rem', padding: '0 6px' }}
                      onClick={() => handlePendingUpiCollection(o)}
                    >
                      <QrCode size={15} /> Collect UPI
                    </button>
                    {o.whatsapp_url && (
                      <a
                        href={o.whatsapp_url}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-whatsapp"
                        style={{ height: '40px', minHeight: '40px', fontSize: '0.82rem', padding: '0 6px', textDecoration: 'none' }}
                      >
                        <Send size={14} /> Send Bill
                      </a>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* ORDER HISTORY */}
        {tab === 'history' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ fontSize: '1.1rem' }}>Order History</h3>
              <button onClick={loadMyOrders} className="btn btn-secondary" style={{ minHeight: '36px', padding: '6px 12px' }}>
                <RefreshCw size={16} /> Refresh
              </button>
            </div>

            {/* History Filter Tabs */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '14px', overflowX: 'auto' }}>
              <button
                className={`btn ${historyFilter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ height: '34px', minHeight: '34px', padding: '0 12px', fontSize: '0.82rem' }}
                onClick={() => setHistoryFilter('all')}
              >
                All ({myOrders.length})
              </button>
              <button
                className={`btn ${historyFilter === 'active' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ height: '34px', minHeight: '34px', padding: '0 12px', fontSize: '0.82rem' }}
                onClick={() => setHistoryFilter('active')}
              >
                Active ({myOrders.filter(o => o.order_status === 'Active').length})
              </button>
              <button
                className={`btn ${historyFilter === 'cancelled' ? 'btn-primary' : 'btn-secondary'}`}
                style={{
                  height: '34px', minHeight: '34px', padding: '0 12px', fontSize: '0.82rem',
                  backgroundColor: historyFilter === 'cancelled' ? '#dc2626' : undefined,
                  borderColor: historyFilter === 'cancelled' ? '#dc2626' : undefined,
                  color: historyFilter === 'cancelled' ? '#fff' : '#b91c1c'
                }}
                onClick={() => setHistoryFilter('cancelled')}
              >
                Cancelled ({myOrders.filter(o => o.order_status === 'Cancelled').length})
              </button>
            </div>

            {myOrders.length === 0 ? (
              <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                No orders recorded yet.
              </div>
            ) : (
              myOrders
                .filter(o => {
                  if (historyFilter === 'active') return o.order_status === 'Active';
                  if (historyFilter === 'cancelled') return o.order_status === 'Cancelled';
                  return true;
                })
                .map(o => (
                  <div
                    key={o.id}
                    className="card"
                    style={{
                      borderLeft: o.order_status === 'Cancelled' ? '4px solid #ef4444' : undefined,
                      backgroundColor: o.order_status === 'Cancelled' ? '#fffafb' : '#fff',
                      opacity: o.order_status === 'Cancelled' ? 0.92 : 1
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontWeight: 'bold' }}>{o.bill_no}</span>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        {o.order_status === 'Cancelled' && (
                          <span className="chip chip-cancelled">Cancelled</span>
                        )}
                        <span className={`chip chip-${o.payment_status.toLowerCase()}`}>
                          {o.payment_status}
                        </span>
                      </div>
                    </div>

                    <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                      👤 {o.buyer_name} ({o.buyer_phone}) • {o.nagar_name || 'N/A'}
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold' }}>
                      <span>Total: ₹{o.total}</span>
                      <span style={{ color: o.balance > 0 ? 'var(--danger)' : 'var(--success)' }}>
                        Bal: ₹{o.balance}
                      </span>
                    </div>

                    {o.order_status === 'Cancelled' && (
                      <div style={{ marginTop: '10px', fontSize: '0.82rem', color: '#991b1b', background: '#fee2e2', padding: '8px 10px', borderRadius: '6px', border: '1px solid #fecaca' }}>
                        <div style={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <XCircle size={14} color="#dc2626" /> Order Cancelled by Admin (Read-Only)
                        </div>
                        {o.cancel_reason && <div style={{ marginTop: '2px' }}>Reason: {o.cancel_reason}</div>}
                        <div style={{ fontSize: '0.74rem', color: '#7f1d1d', marginTop: '4px' }}>
                          Stock returned to common pool. Sellers cannot edit or revert cancelled orders.
                        </div>
                      </div>
                    )}

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '10px' }}>
                      {o.whatsapp_url && o.order_status === 'Active' && (
                        <a
                          href={o.whatsapp_url}
                          target="_blank"
                          rel="noreferrer"
                          className="btn btn-whatsapp"
                          style={{ textDecoration: 'none', height: '40px', minHeight: '40px', fontSize: '0.85rem' }}
                        >
                          <Send size={14} /> WhatsApp
                        </a>
                      )}
                      <button
                        type="button"
                        onClick={() => api.downloadPdf(o.id, o.bill_no)}
                        className="btn btn-secondary"
                        style={{
                          height: '40px', minHeight: '40px', fontSize: '0.85rem',
                          gridColumn: o.order_status === 'Cancelled' || !o.whatsapp_url ? 'span 2' : 'span 1',
                          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px'
                        }}
                      >
                        <Download size={14} /> Download PDF
                      </button>
                    </div>
                  </div>
                ))
            )}
          </div>
        )}

        {/* STOCK STATUS */}
        {tab === 'stock' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ fontSize: '1.1rem' }}>Common Stock Status</h3>
              <button onClick={loadCatalogue} className="btn btn-secondary" style={{ minHeight: '36px', padding: '6px 12px' }}>
                <RefreshCw size={16} /> Refresh
              </button>
            </div>

            {catalogue.items.map(item => (
              <div key={item.id} className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 'bold', fontSize: '1.05rem' }}>{item.name}</span>
                  <span style={{ color: 'var(--primary)', fontWeight: 'bold' }}>₹{item.price}</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px' }}>
                  {item.sizes.map(s => (
                    <div
                      key={s.id}
                      style={{
                        padding: '8px',
                        background: s.stock_qty <= 0 ? '#fee2e2' : '#f8fafc',
                        border: '1px solid var(--border)',
                        borderRadius: '6px',
                        textAlign: 'center'
                      }}
                    >
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Size {s.size}</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 'bold', color: s.stock_qty <= 0 ? 'var(--danger)' : 'var(--text-main)' }}>
                        {s.stock_qty}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      )}
    </div>
  );
}
