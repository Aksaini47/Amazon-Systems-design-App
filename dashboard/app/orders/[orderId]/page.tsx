'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { api, type OrderDetail } from '@/lib/api';
import Link from 'next/link';

function VideoPlayer({ videoId, label }: { videoId: number; label: string }) {
  return (
    <div className="bg-gray-800 rounded-xl overflow-hidden">
      <div className="px-4 py-2 border-b border-gray-700 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-300">{label}</span>
      </div>
      <video
        controls
        className="w-full max-h-64 bg-black"
        src={api.videoStreamUrl(videoId)}
      />
    </div>
  );
}

type ImageRecord = { id: number; file_name: string; captured_at: string };

function ImageGallery({ images }: { images: ImageRecord[] }) {
  const [lightbox, setLightbox] = useState<ImageRecord | null>(null);

  return (
    <div className="mb-6">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">
        Evidence Photos
        <span className="ml-2 text-xs font-normal text-gray-600">{images.length} photo{images.length !== 1 ? 's' : ''}</span>
      </h2>
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
        {images.map(img => (
          <button
            key={img.id}
            onClick={() => setLightbox(img)}
            className="aspect-square rounded-lg overflow-hidden bg-gray-800 border border-gray-700 hover:border-blue-500 transition-colors group relative"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={api.imageUrl(img.id)}
              alt={img.file_name}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
            />
          </button>
        ))}
      </div>

      {/* Lightbox */}
      {lightbox && (
        <div
          className="fixed inset-0 bg-black/90 flex items-center justify-center z-50 p-4"
          onClick={() => setLightbox(null)}
        >
          <div className="relative max-w-4xl w-full" onClick={e => e.stopPropagation()}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={api.imageUrl(lightbox.id)}
              alt={lightbox.file_name}
              className="w-full max-h-[80vh] object-contain rounded-xl"
            />
            <div className="flex items-center justify-between mt-3 px-1">
              <span className="text-gray-400 text-xs font-mono">{lightbox.file_name}</span>
              <span className="text-gray-500 text-xs">
                {new Date(lightbox.captured_at).toLocaleString()}
              </span>
            </div>
            <button
              onClick={() => setLightbox(null)}
              className="absolute -top-3 -right-3 w-8 h-8 bg-gray-800 rounded-full flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-700 transition-colors text-lg font-light"
            >
              ×
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const CLAIM_STATUSES = ['none', 'pending', 'filed', 'resolved'] as const;
const STATUS_COLORS: Record<string, string> = {
  none: 'bg-gray-800 text-gray-400',
  pending: 'bg-yellow-900 text-yellow-300',
  filed: 'bg-blue-900 text-blue-300',
  resolved: 'bg-green-900 text-green-300',
};

export default function OrderDetailPage() {
  const params = useParams();
  const orderId = params.orderId as string;
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [claimModal, setClaimModal] = useState(false);

  useEffect(() => {
    api.getOrder(orderId)
      .then(setOrder)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [orderId]);

  async function updateClaim(returnId: number, status: string) {
    await api.updateClaimStatus(returnId, status);
    const updated = await api.getOrder(orderId);
    setOrder(updated);
  }

  if (loading) return <div className="text-center py-20 text-gray-500">Loading...</div>;
  if (!order) return <div className="text-center py-20 text-gray-500">Order not found</div>;

  const packingVideo = order.videos.find(v => v.type === 'packing');
  const unpackingVideo = order.videos.find(v => v.type === 'unpacking');

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-gray-500 hover:text-white text-sm">Orders</Link>
          <span className="text-gray-700">/</span>
          <span className="text-white font-mono text-sm">{orderId}</span>
        </div>
        <a
          href={api.exportOrderUrl(orderId)}
          download
          className="bg-gray-700 hover:bg-gray-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
          </svg>
          Export ZIP
        </a>
      </div>

      <div className="grid grid-cols-2 gap-6 mb-6">
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-xs uppercase tracking-wide text-gray-500 mb-3">Order Info</h2>
          <p className="text-white font-medium mb-1">{order.product_title || '—'}</p>
          <p className="text-gray-400 text-sm">ASIN: {order.asin || '—'}</p>
          <p className="text-gray-400 text-sm">SKU: {order.sku || '—'}</p>
          <p className="text-gray-400 text-sm">Qty: {order.quantity || '—'}</p>
          <p className="text-gray-400 text-sm mt-2">
            {order.purchase_date ? new Date(order.purchase_date).toLocaleDateString('en-IN', { dateStyle: 'long' }) : '—'}
          </p>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-xs uppercase tracking-wide text-gray-500 mb-3">Shipment</h2>
          {order.awbs.length > 0 ? order.awbs.map(a => (
            <div key={a.awb_number} className="mb-2">
              <p className="font-mono text-blue-400 text-sm">{a.awb_number}</p>
              <p className="text-gray-500 text-xs">{a.carrier || 'Carrier unknown'}</p>
            </div>
          )) : <p className="text-gray-600 text-sm">No AWB on record</p>}

          <div className="mt-3 flex items-center gap-2">
            <span className={`text-xs px-2 py-1 rounded-full ${order.has_return ? 'bg-red-900 text-red-300' : 'bg-gray-800 text-gray-400'}`}>
              {order.has_return ? 'Has Return' : 'No Return'}
            </span>
            <span className={`text-xs px-2 py-1 rounded-full ${order.fulfillment_channel === 'MFN' ? 'bg-purple-900 text-purple-300' : 'bg-gray-800 text-gray-400'}`}>
              {order.fulfillment_channel === 'MFN' ? 'FBM' : order.fulfillment_channel || '—'}
            </span>
          </div>
        </div>
      </div>

      {/* Videos */}
      <div className="mb-6">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">Videos</h2>
        {!packingVideo && !unpackingVideo ? (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-8 text-center text-gray-600 text-sm">
            No videos recorded yet for this order
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            {packingVideo && <VideoPlayer videoId={packingVideo.id} label="Packing Video" />}
            {unpackingVideo && <VideoPlayer videoId={unpackingVideo.id} label="Unpacking Video" />}
          </div>
        )}
      </div>

      {/* Images / Evidence Photos */}
      {order.images.length > 0 && (
        <ImageGallery images={order.images} />
      )}


      {order.returns.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-300">Returns</h2>
            {(packingVideo || unpackingVideo) && (
              <button
                onClick={() => setClaimModal(true)}
                className="bg-red-700 hover:bg-red-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
              >
                Claim Helper
              </button>
            )}
          </div>
          <div className="space-y-3">
            {order.returns.map(ret => (
              <div key={ret.id} className="bg-gray-900 rounded-xl border border-gray-800 p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-gray-400 text-xs">Return date: {ret.return_date || '—'}</p>
                    <p className="text-gray-400 text-xs">Reason: {ret.reason_code || '—'}</p>
                    <p className="text-gray-400 text-xs">RMA: {ret.amazon_rma_id || '—'}</p>
                    <p className="text-gray-400 text-xs">Refund: ₹{ret.refund_amount || 0}</p>
                  </div>
                  <select
                    value={ret.claim_status}
                    onChange={e => updateClaim(ret.id, e.target.value)}
                    className={`text-xs px-2 py-1 rounded-full border-0 outline-none cursor-pointer ${STATUS_COLORS[ret.claim_status]}`}
                  >
                    {CLAIM_STATUSES.map(s => (
                      <option key={s} value={s} className="bg-gray-900 text-white">{s}</option>
                    ))}
                  </select>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Claim Helper Modal */}
      {claimModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-6" onClick={() => setClaimModal(false)}>
          <div className="bg-gray-900 rounded-2xl border border-gray-700 p-8 max-w-3xl w-full" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-white mb-2">Claim Helper</h2>
            <p className="text-gray-500 text-sm mb-6">Open Amazon Seller Central → A-to-Z or SAFE-T Claims → paste this Order ID → upload the video below.</p>

            <div className="bg-gray-800 rounded-xl p-4 mb-6 flex items-center justify-between">
              <span className="font-mono text-2xl text-blue-400 font-bold">{orderId}</span>
              <button
                onClick={() => navigator.clipboard.writeText(orderId)}
                className="text-gray-400 hover:text-white text-xs border border-gray-700 px-3 py-1.5 rounded-lg transition-colors"
              >
                Copy
              </button>
            </div>

            {packingVideo && <VideoPlayer videoId={packingVideo.id} label="Packing Video" />}
            {unpackingVideo && <div className="mt-4"><VideoPlayer videoId={unpackingVideo.id} label="Unpacking Video" /></div>}

            <button onClick={() => setClaimModal(false)} className="mt-6 w-full text-gray-500 hover:text-white text-sm transition-colors">
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
