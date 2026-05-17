'use client';

import { useEffect, useState } from 'react';
import { api, type Order } from '@/lib/api';
import Link from 'next/link';

const EMPTY_FORM = {
  order_id: '', product_title: '', purchase_date: '',
  order_status: 'Shipped', fulfillment_channel: 'MFN',
  asin: '', sku: '', quantity: '1', awb_number: '', carrier: '',
};

function AddOrderModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  function set(key: string, value: string) {
    setForm(f => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await api.createOrder({
        ...form,
        quantity: parseInt(form.quantity) || 1,
        purchase_date: form.purchase_date || new Date().toISOString(),
      });
      onSaved();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save order');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-gray-900 rounded-2xl border border-gray-700 p-6 w-full max-w-lg" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-white mb-4">Add Order Manually</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-xs text-gray-400 block mb-1">Order ID *</label>
              <input
                value={form.order_id}
                onChange={e => set('order_id', e.target.value)}
                placeholder="403-1234567-1234567"
                required
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white font-mono placeholder-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-gray-400 block mb-1">Product Title</label>
              <input
                value={form.product_title}
                onChange={e => set('product_title', e.target.value)}
                placeholder="Product name..."
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Purchase Date</label>
              <input
                type="date"
                value={form.purchase_date}
                onChange={e => set('purchase_date', e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Status</label>
              <select
                value={form.order_status}
                onChange={e => set('order_status', e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
              >
                {['Pending', 'Unshipped', 'Shipped', 'Delivered', 'Canceled'].map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Fulfillment</label>
              <select
                value={form.fulfillment_channel}
                onChange={e => set('fulfillment_channel', e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="MFN">FBM (MFN)</option>
                <option value="AFN">FBA (AFN)</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Qty</label>
              <input
                type="number"
                min="1"
                value={form.quantity}
                onChange={e => set('quantity', e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">ASIN</label>
              <input
                value={form.asin}
                onChange={e => set('asin', e.target.value)}
                placeholder="B0XXXXXXXXX"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">SKU</label>
              <input
                value={form.sku}
                onChange={e => set('sku', e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">AWB Number</label>
              <input
                value={form.awb_number}
                onChange={e => set('awb_number', e.target.value)}
                placeholder="Tracking / AWB"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Carrier</label>
              <input
                value={form.carrier}
                onChange={e => set('carrier', e.target.value)}
                placeholder="Delhivery, DTDC..."
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          {error && <p className="text-red-400 text-xs">{error}</p>}

          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium py-2 rounded-lg transition-colors"
            >
              {saving ? 'Saving...' : 'Save Order'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function OrdersPage() {
  const PAGE_SIZE = 50;
  const [orders, setOrders] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | 'returns'>('all');
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [addModal, setAddModal] = useState(false);
  const [page, setPage] = useState(0); // zero-based

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  async function load(q?: string, hasReturn?: boolean, p = 0) {
    setLoading(true);
    try {
      const params: Record<string, string> = {
        limit: String(PAGE_SIZE),
        offset: String(p * PAGE_SIZE),
      };
      if (q) params.search = q;
      if (hasReturn) params.has_return = '1';
      const data = await api.getOrders(params);
      setOrders(data.orders);
      setTotal(data.total);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  // Reset to page 0 whenever search or filter changes
  useEffect(() => {
    setPage(0);
    load(search, filter === 'returns', 0);
  }, [search, filter]);

  // Load whenever page changes (but not on initial mount, that's handled above)
  const isFirstRender = typeof window !== 'undefined';
  useEffect(() => {
    load(search, filter === 'returns', page);
  }, [page]);

  async function handleSync() {
    setSyncing(true);
    try {
      await api.triggerSync('all');
      setTimeout(() => load(search, filter === 'returns', page), 3000);
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      {addModal && (
        <AddOrderModal onClose={() => setAddModal(false)} onSaved={() => load(search, filter === 'returns')} />
      )}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Orders</h1>
          <p className="text-gray-500 text-sm mt-1">{total} total orders</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setAddModal(true)}
            className="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            + Add Order
          </button>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {syncing ? 'Syncing...' : 'Sync Now'}
          </button>
        </div>
      </div>

      <div className="flex gap-3 mb-4">
        <input
          type="text"
          placeholder="Search order ID, product, SKU..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
        />
        <div className="flex rounded-lg overflow-hidden border border-gray-700">
          {(['all', 'returns'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 text-sm font-medium transition-colors capitalize ${filter === f ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
                }`}
            >
              {f === 'returns' ? 'Has Return' : 'All'}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-500">Loading orders...</div>
      ) : orders.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p className="text-lg">No orders found</p>
          <p className="text-sm mt-2">Click Sync Now or configure SP-API credentials to import orders</p>
        </div>
      ) : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
                <th className="text-left px-4 py-3">Order ID</th>
                <th className="text-left px-4 py-3">Product</th>
                <th className="text-left px-4 py-3">Date</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Type</th>
                <th className="text-left px-4 py-3">Return</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {orders.map(order => (
                <tr key={order.order_id} className="hover:bg-gray-800/50 transition-colors">
                  <td className="px-4 py-3 font-mono text-blue-400 text-xs">{order.order_id}</td>
                  <td className="px-4 py-3 text-gray-200 max-w-xs truncate">
                    {order.product_title || <span className="text-gray-600">—</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {order.purchase_date ? new Date(order.purchase_date).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-1 rounded-full ${order.order_status === 'Shipped' ? 'bg-green-900 text-green-300' :
                      order.order_status === 'Unshipped' ? 'bg-yellow-900 text-yellow-300' :
                        'bg-gray-800 text-gray-400'
                      }`}>
                      {order.order_status || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{order.fulfillment_channel || '—'}</td>
                  <td className="px-4 py-3">
                    {order.has_return ? (
                      <span className="text-xs px-2 py-1 rounded-full bg-red-900 text-red-300">Return</span>
                    ) : (
                      <span className="text-gray-700 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/orders/${order.order_id}`}
                      className="text-blue-500 hover:text-blue-400 text-xs font-medium"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
              <span className="text-xs text-gray-500">
                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total} orders
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-800 text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  ← Previous
                </button>
                <span className="px-3 py-1.5 text-xs text-gray-500">
                  Page {page + 1} / {totalPages}
                </span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-800 text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
