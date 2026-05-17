'use client';

import { useEffect, useState } from 'react';
import { api, type Return } from '@/lib/api';
import Link from 'next/link';

const STATUS_COLORS: Record<string, string> = {
  none: 'bg-gray-800 text-gray-400',
  pending: 'bg-yellow-900 text-yellow-300',
  filed: 'bg-blue-900 text-blue-300',
  resolved: 'bg-green-900 text-green-300',
};

export default function ReturnsPage() {
  const [returns, setReturns] = useState<Return[]>([]);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState<string>('');
  const [loading, setLoading] = useState(true);

  async function load(claimStatus?: string) {
    setLoading(true);
    try {
      const params: Record<string, string> = { limit: '100' };
      if (claimStatus) params.claim_status = claimStatus;
      const data = await api.getReturns(params);
      setReturns(data.returns);
      setTotal(data.total);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(filter || undefined); }, [filter]);

  async function updateClaim(ret: Return, status: string) {
    await api.updateClaimStatus(ret.id, status);
    load(filter || undefined);
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Returns</h1>
          <p className="text-gray-500 text-sm mt-1">{total} return records</p>
        </div>
      </div>

      <div className="flex gap-2 mb-4 flex-wrap">
        {[['', 'All'], ['none', 'Unfiled'], ['pending', 'Pending'], ['filed', 'Filed'], ['resolved', 'Resolved']].map(([val, label]) => (
          <button
            key={val}
            onClick={() => setFilter(val)}
            className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
              filter === val ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-500">Loading returns...</div>
      ) : returns.length === 0 ? (
        <div className="text-center py-20 text-gray-500">No returns found</div>
      ) : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
                <th className="text-left px-4 py-3">Order ID</th>
                <th className="text-left px-4 py-3">Product</th>
                <th className="text-left px-4 py-3">Return Date</th>
                <th className="text-left px-4 py-3">Reason</th>
                <th className="text-left px-4 py-3">Refund</th>
                <th className="text-left px-4 py-3">Claim</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {returns.map(ret => (
                <tr key={ret.id} className="hover:bg-gray-800/50 transition-colors">
                  <td className="px-4 py-3 font-mono text-blue-400 text-xs">{ret.order_id}</td>
                  <td className="px-4 py-3 text-gray-300 max-w-xs truncate text-xs">
                    {ret.product_title || '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {ret.return_date ? new Date(ret.return_date).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{ret.reason_code || '—'}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">₹{ret.refund_amount || 0}</td>
                  <td className="px-4 py-3">
                    <select
                      value={ret.claim_status}
                      onChange={e => updateClaim(ret, e.target.value)}
                      className={`text-xs px-2 py-1 rounded-full border-0 outline-none cursor-pointer ${STATUS_COLORS[ret.claim_status]}`}
                    >
                      {['none', 'pending', 'filed', 'resolved'].map(s => (
                        <option key={s} value={s} className="bg-gray-900 text-white">{s}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/orders/${ret.order_id}`} className="text-blue-500 hover:text-blue-400 text-xs font-medium">
                      View Order
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
