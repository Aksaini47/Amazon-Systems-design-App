const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

export type Order = {
  order_id: string;
  purchase_date: string;
  order_status: string;
  fulfillment_channel: string;
  asin: string;
  sku: string;
  product_title: string;
  quantity: number;
  marketplace_id: string;
  has_return: number;
  synced_at: string;
};

export type Video = {
  id: number;
  order_id: string;
  type: 'packing' | 'unpacking';
  file_name: string;
  duration_seconds: number;
  file_size_bytes: number;
  recorded_at: string;
  uploaded_at: string;
};

export type Return = {
  id: number;
  order_id: string;
  return_date: string;
  amazon_rma_id: string;
  return_tracking: string;
  reason_code: string;
  refund_amount: number;
  claim_status: 'none' | 'pending' | 'filed' | 'resolved';
  product_title?: string;
};

export type FbaShipment = {
  shipment_id: string;
  shipment_name: string | null;
  destination_fc: string | null;
  shipment_status: string;
  unit_count: number;
  created_date: string | null;
  synced_at: string | null;
  video_count: number;
};

export type FbaShipmentDetail = FbaShipment & {
  videos: Array<Video & { fba_box_number: number | null }>;
};

export type OrderDetail = Order & {
  videos: Video[];
  images: Array<{ id: number; file_name: string; captured_at: string }>;
  returns: Return[];
  awbs: Array<{ awb_number: string; carrier: string }>;
};

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `API error ${res.status}`);
  }
  return res.json();
}

export const api = {
  createOrder: (data: Record<string, unknown>) =>
    apiFetch('/api/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  getOrders: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return apiFetch<{ orders: Order[]; total: number }>(`/api/orders${qs}`);
  },

  getOrder: (orderId: string) =>
    apiFetch<OrderDetail>(`/api/orders/${orderId}`),

  getOrderByAwb: (awb: string) =>
    apiFetch<Order & { awb_number: string }>(`/api/orders/by-awb/${awb}`),

  getReturns: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return apiFetch<{ returns: Return[]; total: number }>(`/api/returns${qs}`);
  },

  updateClaimStatus: (returnId: number, claim_status: string) =>
    apiFetch(`/api/returns/${returnId}/claim-status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ claim_status }),
    }),

  triggerSync: (type: 'all' | 'orders' | 'returns' = 'all') =>
    apiFetch(`/api/sync/trigger`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type }),
    }),

  getSyncStatus: () =>
    apiFetch<Array<{ job_name: string; last_run: string; status: string; message: string }>>('/api/sync/status'),

  getFbaShipments: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return apiFetch<{ shipments: FbaShipment[]; total: number }>(`/api/fba-shipments${qs}`);
  },

  getFbaShipment: (shipmentId: string) =>
    apiFetch<FbaShipmentDetail>(`/api/fba-shipments/${shipmentId}`),

  createFbaShipment: (data: Record<string, unknown>) =>
    apiFetch('/api/fba-shipments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  videoStreamUrl: (videoId: number) => `${API_BASE}/api/videos/${videoId}/stream`,
  imageUrl: (imageId: number) => `${API_BASE}/api/images/${imageId}`,
  exportOrderUrl: (orderId: string) => `${API_BASE}/api/orders/${orderId}/export`,
  exportFbaUrl: (shipmentId: string) => `${API_BASE}/api/fba-shipments/${shipmentId}/export`,
};
