'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { api, type FbaShipmentDetail, type Video } from '@/lib/api';
import Link from 'next/link';

const STATUS_COLORS: Record<string, string> = {
  WORKING:    'bg-yellow-900 text-yellow-300',
  SHIPPED:    'bg-blue-900 text-blue-300',
  IN_TRANSIT: 'bg-blue-900 text-blue-300',
  RECEIVING:  'bg-purple-900 text-purple-300',
  CLOSED:     'bg-green-900 text-green-300',
};

function VideoCard({ video }: { video: Video & { fba_box_number: number | null } }) {
  const [playing, setPlaying] = useState(false);
  const url = api.videoStreamUrl(video.id);
  const duration = video.duration_seconds
    ? `${Math.floor(video.duration_seconds / 60)}:${String(Math.round(video.duration_seconds % 60)).padStart(2, '0')}`
    : null;
  const size = video.file_size_bytes
    ? `${(video.file_size_bytes / (1024 * 1024)).toFixed(1)} MB`
    : null;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      <div className="aspect-video bg-black relative">
        {playing ? (
          <video src={url} controls autoPlay className="w-full h-full object-contain" />
        ) : (
          <button onClick={() => setPlaying(true)}
            className="absolute inset-0 flex flex-col items-center justify-center gap-2 hover:bg-white/5 transition-colors">
            <div className="w-14 h-14 bg-white/10 rounded-full flex items-center justify-center">
              <svg className="w-6 h-6 text-white ml-1" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
            </div>
          </button>
        )}
      </div>
      <div className="p-3 flex items-center justify-between">
        <div>
          {video.fba_box_number != null && (
            <span className="text-xs font-mono text-blue-400 mr-2">Box {video.fba_box_number}</span>
          )}
          <span className="text-xs text-gray-400">
            {new Date(video.recorded_at).toLocaleString()}
          </span>
          {(duration || size) && (
            <span className="text-xs text-gray-600 ml-2">
              {[duration, size].filter(Boolean).join(' · ')}
            </span>
          )}
        </div>
        <a href={url} download className="text-xs text-blue-500 hover:text-blue-400 font-medium">Download</a>
      </div>
    </div>
  );
}

export default function FbaShipmentDetailPage() {
  const { shipmentId } = useParams<{ shipmentId: string }>();
  const [shipment, setShipment] = useState<FbaShipmentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.getFbaShipment(shipmentId)
      .then(setShipment)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [shipmentId]);

  if (loading) return <div className="text-center py-20 text-gray-500">Loading...</div>;
  if (error) return <div className="text-center py-20 text-red-400">{error}</div>;
  if (!shipment) return null;

  // Group videos by box number
  const byBox = shipment.videos.reduce<Record<string, typeof shipment.videos>>((acc, v) => {
    const key = v.fba_box_number != null ? `Box ${v.fba_box_number}` : 'General';
    (acc[key] = acc[key] || []).push(v);
    return acc;
  }, {});

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-6">
        <Link href="/fba" className="text-gray-500 hover:text-gray-300 text-sm">← FBA Shipments</Link>
      </div>

      {/* Header */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-xl font-bold text-white font-mono">{shipment.shipment_id}</h1>
              <span className={`text-xs px-2 py-1 rounded-full ${STATUS_COLORS[shipment.shipment_status] ?? 'bg-gray-800 text-gray-400'}`}>
                {shipment.shipment_status}
              </span>
            </div>
            {shipment.shipment_name && (
              <p className="text-gray-400 text-sm mb-3">{shipment.shipment_name}</p>
            )}
            <div className="flex gap-6 text-sm">
              {shipment.destination_fc && (
                <div>
                  <span className="text-gray-500 text-xs block">Destination FC</span>
                  <span className="text-white font-mono">{shipment.destination_fc}</span>
                </div>
              )}
              <div>
                <span className="text-gray-500 text-xs block">Units</span>
                <span className="text-white">{shipment.unit_count}</span>
              </div>
              <div>
                <span className="text-gray-500 text-xs block">Videos</span>
                <span className="text-white">{shipment.videos.length}</span>
              </div>
              {shipment.created_date && (
                <div>
                  <span className="text-gray-500 text-xs block">Created</span>
                  <span className="text-white">{new Date(shipment.created_date).toLocaleDateString()}</span>
                </div>
              )}
            </div>
          </div>
          <a
            href={api.exportFbaUrl(shipment.shipment_id)}
            className="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            Export ZIP
          </a>
        </div>
      </div>

      {/* Videos grouped by box */}
      {shipment.videos.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p className="text-lg">No videos yet</p>
          <p className="text-sm mt-2">Record packing videos in the mobile app using this Shipment ID</p>
          <p className="mt-3 font-mono text-blue-400 text-sm select-all">{shipment.shipment_id}</p>
        </div>
      ) : (
        Object.entries(byBox).map(([boxLabel, videos]) => (
          <div key={boxLabel} className="mb-8">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">{boxLabel}</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {videos.map(v => <VideoCard key={v.id} video={v} />)}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
