const axios = require('axios');

const TOKEN_URL = 'https://api.amazon.com/auth/o2/token';
const BASE_URL = 'https://sellingpartnerapi-in.amazon.com'; // India endpoint

// Marketplace IDs reference:
// India: A21TJRUUN4KGV | US: ATVPDKIKX0DER | UK: A1F83G8C2ARO7P
// Germany: A1PA6795UKMFR | France: A13V1IB3VIYZZH | UAE: A2VIGQ35RCS4UG

let cachedToken = null;
let tokenExpiresAt = 0;

async function getAccessToken() {
  const now = Date.now();
  // Refresh if token expires within 60 seconds
  if (cachedToken && now < tokenExpiresAt - 60000) {
    return cachedToken;
  }

  const response = await axios.post(TOKEN_URL, new URLSearchParams({
    grant_type: 'refresh_token',
    refresh_token: process.env.AMAZON_REFRESH_TOKEN,
    client_id: process.env.AMAZON_CLIENT_ID,
    client_secret: process.env.AMAZON_CLIENT_SECRET,
  }), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });

  cachedToken = response.data.access_token;
  tokenExpiresAt = now + response.data.expires_in * 1000;
  return cachedToken;
}

function makeHeaders(token) {
  return {
    'x-amz-access-token': token,
    'x-amz-date': new Date().toISOString(),
    'Content-Type': 'application/json',
  };
}

// Fetch orders created or updated after a given date
// Uses Orders API v2026-01-01 with packages included
async function fetchOrders(createdAfter) {
  const token = await getAccessToken();
  const marketplaceId = process.env.AMAZON_MARKETPLACE_ID;

  const params = new URLSearchParams({
    MarketplaceIds: marketplaceId,
    CreatedAfter: createdAfter,
    MaxResultsPerPage: '100',
  });

  const orders = [];
  let nextToken = null;

  do {
    if (nextToken) params.set('NextToken', nextToken);

    // Try v2026-01-01 first, fall back to v0 if not available
    const url = `${BASE_URL}/orders/v0/orders?${params}`;
    const res = await axios.get(url, { headers: makeHeaders(token) });

    const payload = res.data.payload;
    orders.push(...(payload.Orders || []));
    nextToken = payload.NextToken;

    // Rate limit: wait briefly between paginated requests
    if (nextToken) await sleep(500);
  } while (nextToken);

  return orders;
}

// Fetch order items (ASIN, SKU, title, qty) for a specific order
async function fetchOrderItems(orderId) {
  const token = await getAccessToken();
  const url = `${BASE_URL}/orders/v0/orders/${orderId}/orderItems`;
  const res = await axios.get(url, { headers: makeHeaders(token) });
  return res.data.payload.OrderItems || [];
}

// Fetch shipment/package info for a specific order (AWB tracking numbers)
async function fetchOrderPackages(orderId) {
  const token = await getAccessToken();
  // v0 endpoint for package/tracking info
  const url = `${BASE_URL}/orders/v0/orders/${orderId}/shipment`;
  try {
    const res = await axios.get(url, { headers: makeHeaders(token) });
    return res.data.payload || null;
  } catch {
    return null; // Not all orders have shipment info
  }
}

// Request a returns report (async — returns reportId to poll)
async function requestReturnsReport(startDate, endDate) {
  const token = await getAccessToken();
  const url = `${BASE_URL}/reports/2021-06-30/reports`;

  const body = {
    reportType: 'GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE',
    dataStartTime: startDate,
    dataEndTime: endDate,
    marketplaceIds: [process.env.AMAZON_MARKETPLACE_ID],
  };

  const res = await axios.post(url, body, { headers: makeHeaders(token) });
  return res.data.reportId;
}

// Poll report status until done
async function waitForReport(reportId, maxWaitMs = 300000) {
  const token = await getAccessToken();
  const start = Date.now();

  while (Date.now() - start < maxWaitMs) {
    const url = `${BASE_URL}/reports/2021-06-30/reports/${reportId}`;
    const res = await axios.get(url, { headers: makeHeaders(token) });
    const status = res.data.processingStatus;

    if (status === 'DONE') return res.data.reportDocumentId;
    if (status === 'FATAL' || status === 'CANCELLED') throw new Error(`Report ${reportId} failed: ${status}`);

    await sleep(15000); // Poll every 15 seconds
  }

  throw new Error(`Report ${reportId} timed out after ${maxWaitMs}ms`);
}

// Download report content
async function downloadReport(reportDocumentId) {
  const token = await getAccessToken();
  const metaUrl = `${BASE_URL}/reports/2021-06-30/documents/${reportDocumentId}`;
  const metaRes = await axios.get(metaUrl, { headers: makeHeaders(token) });

  const { url } = metaRes.data;
  const dataRes = await axios.get(url, { responseType: 'text' });
  return dataRes.data;
}

// Fetch FBA inbound shipments (seller → Amazon warehouse)
async function fetchFbaShipments(statuses = ['WORKING', 'SHIPPED', 'IN_TRANSIT', 'RECEIVING']) {
  const token = await getAccessToken();
  const marketplaceId = process.env.AMAZON_MARKETPLACE_ID;

  const params = new URLSearchParams({
    MarketplaceId: marketplaceId,
    ShipmentStatusList: statuses.join(','),
    QueryType: 'SHIPMENT',
  });

  const url = `${BASE_URL}/fba/inbound/v0/shipments?${params}`;
  const res = await axios.get(url, { headers: makeHeaders(token) });
  return res.data.payload?.ShipmentData || [];
}

// Fetch item details for a specific FBA inbound shipment
async function fetchFbaShipmentItems(shipmentId) {
  const token = await getAccessToken();
  const marketplaceId = process.env.AMAZON_MARKETPLACE_ID;

  const params = new URLSearchParams({ MarketplaceId: marketplaceId });
  const url = `${BASE_URL}/fba/inbound/v0/shipments/${shipmentId}/items?${params}`;
  const res = await axios.get(url, { headers: makeHeaders(token) });
  return res.data.payload?.ItemData || [];
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

module.exports = { fetchOrders, fetchOrderItems, fetchOrderPackages, requestReturnsReport, waitForReport, downloadReport, fetchFbaShipments, fetchFbaShipmentItems };
