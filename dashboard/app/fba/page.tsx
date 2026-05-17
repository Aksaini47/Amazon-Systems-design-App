'use client';

import { useEffect, useState } from 'react';
import { api, type FbaShipment } from '@/lib/api';
import Link from 'next/link';

const STATUS_COLORS: Record<string, string> = {
  WORKING:    'bg-yellow-900 text-yellow-300',
  SHIPPED:    'bg-blue-900 text-blue-300',
  IN_TRANSIT: 'bg-blue-900 text-blue-300',
  RECEIVING:  'bg-purple-900 text-purple-300',
  CLOSED:     'bg-green-900 text-green-300',
  CANCELLED:  'bg-gray-800 text-gray-500',
};

const EMPTY_FORM = { shipment_id: '', shipment_name: '', destination_fc: '', unit_count: '' };

function AddShipmentModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  function set(k: string, v: string) { setForm(f => ({ ...f, [k]: v })); }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await api.createFbaShipment({ ...form, unit_count: parseInt(form.unit_count) || 0 });
      onSaved();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-gray-900 rounded-2xl border border-gray-700 p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-white mb-4">Add FBA Shipment Manually</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Shipment ID *</label>
            <input value={form.shipment_id} onChange={e => set('shipment_id', e.target.value)} required
              placeholder="FBA15XXXXXXXX"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white font-mono placeholder-gray-600 focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Shipment Name</label>
            <input value={form.shipment_name} onChange={e => set('shipment_name', e.target.value)}
              placeholder="FBA Shipment Name"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Destination FC</label>
              <input value={form.destination_fc} onChange={e => set('destination_fc', e.target.value)}
                placeholder="BOM7"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white font-mono placeholder-gray-600 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Unit Count</label>
              <input type="number" min="0" value={form.unit_count} onChange={e => set('unit_count', e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500" />
            </div>
          </div>
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={saving}
              className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium py-2 rounded-lg transition-colors">
              {saving ? 'Saving...' : 'Save Shipment'}
            </button>
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function FbaPage() {
  const [shipments, setShipments] = useState<FbaShipment[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [addModal, setAddModal] = useState(false);
  const [syncing, setSyncing] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await api.getFbaShipments({ limit: '100' });
      setShipments(data.shipments);
      setTotal(data.total);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleSync() {
    setSyncing(true);
    try {
      await api.triggerSync('fba' as 'all');
      setTimeout(load, 5000);
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      {addModal && <AddShipmentModal onClose={() => setAddModal(false)} onSaved={load} />}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">FBA Shipments</h1>
          <p className="text-gray-500 text-sm mt-1">{total} shipments — packing videos for Amazon warehouse</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setAddModal(true)}
            className="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            + Add Shipment
          </button>
          <button onClick={handleSync} disabled={syncing}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            {syncing ? 'Syncing...' : 'Sync Now'}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-500">Loading shipments...</div>
      ) : shipments.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p className="text-lg">No FBA shipments found</p>
          <p className="text-sm mt-2">Sync from SP-API or add manually</p>
        </div>
      ) : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
                <th className="text-left px-4 py-3">Shipment ID</th>
                <th className="text-left px-4 py-3">Name</th>
                <th className="text-left px-4 py-3">Dest. FC</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Units</th>
                <th className="text-left px-4 py-3">Videos</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {shipments.map(s => (
                <tr key={s.shipment_id} className="hover:bg-gray-800/50 transition-colors">
                  <td className="px-4 py-3 font-mono text-blue-400 text-xs">{s.shipment_id}</td>
                  <td className="px-4 py-3 text-gray-200 max-w-xs truncate">
                    {s.shipment_name || <span className="text-gray-600">—</span>}
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-300 text-xs">{s.destination_fc || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-1 rounded-full ${STATUS_COLORS[s.shipment_status] ?? 'bg-gray-800 text-gray-400'}`}>
                      {s.shipment_status || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-300">{s.unit_count ?? '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium ${s.video_count > 0 ? 'text-green-400' : 'text-gray-600'}`}>
                      {s.video_count} video{s.video_count !== 1 ? 's' : ''}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/fba/${s.shipment_id}`}
                      className="text-blue-500 hover:text-blue-400 text-xs font-medium">
                      View
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
