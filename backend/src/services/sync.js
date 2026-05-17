const cron = require('node-cron');
const { db } = require('../db/db');
const spapi = require('./spapi');

function parseReturnsFlatFile(rawText) {
  const lines = rawText.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split('\t').map(h => h.trim());
  return lines.slice(1).map(line => {
    const values = line.split('\t');
    return Object.fromEntries(headers.map((h, i) => [h, (values[i] || '').trim()]));
  });
}

async function logSync(jobName, status, message) {
  await db.execute({
    sql: `INSERT OR REPLACE INTO sync_log (job_name, last_run, status, message) VALUES (?, datetime('now'), ?, ?)`,
    args: [jobName, status, message],
  });
}

async function syncOrders() {
  await logSync('orders', 'running', 'Syncing orders...');
  try {
    const createdAfter = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    console.log(`[sync] Fetching orders since ${createdAfter}`);

    const orders = await spapi.fetchOrders(createdAfter);
    console.log(`[sync] Got ${orders.length} orders`);

    for (const order of orders) {
      const orderId = order.AmazonOrderId;
      if (!orderId) continue;

      await db.execute({
        sql: `INSERT OR REPLACE INTO orders
                (order_id, purchase_date, order_status, fulfillment_channel, marketplace_id, synced_at)
              VALUES (?, ?, ?, ?, ?, datetime('now'))`,
        args: [orderId, order.PurchaseDate, order.OrderStatus, order.FulfillmentChannel, order.MarketplaceId],
      });

      // Fetch line items
      try {
        const items = await spapi.fetchOrderItems(orderId);
        if (items.length > 0) {
          const item = items[0];
          await db.execute({
            sql: `UPDATE orders SET asin=?, sku=?, product_title=?, quantity=? WHERE order_id=?`,
            args: [item.ASIN, item.SellerSKU, item.Title, parseInt(item.QuantityOrdered) || 1, orderId],
          });
        }
      } catch (e) {
        console.warn(`[sync] Items fetch failed for ${orderId}:`, e.message);
      }

      // For FBM: fetch AWB/tracking
      if (order.FulfillmentChannel === 'MFN') {
        try {
          const shipment = await spapi.fetchOrderPackages(orderId);
          if (shipment?.TrackingNumber) {
            await db.execute({
              sql: `INSERT OR REPLACE INTO awb_mappings (awb_number, order_id, carrier, package_status) VALUES (?, ?, ?, ?)`,
              args: [shipment.TrackingNumber, orderId, shipment.CarrierCode || null, null],
            });
          }
        } catch (e) {
          console.warn(`[sync] Shipment fetch failed for ${orderId}:`, e.message);
        }
      }

      await sleep(300); // Respect SP-API rate limits
    }

    await logSync('orders', 'ok', `Synced ${orders.length} orders`);
    console.log('[sync] Orders sync complete');
  } catch (err) {
    await logSync('orders', 'error', err.message);
    console.error('[sync] Orders sync failed:', err.message);
  }
}

async function syncReturns() {
  await logSync('returns', 'running', 'Requesting returns report...');
  try {
    const endDate = new Date().toISOString();
    const startDate = new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString();

    console.log('[sync] Requesting returns report...');
    const reportId = await spapi.requestReturnsReport(startDate, endDate);
    const docId = await spapi.waitForReport(reportId);
    const rawText = await spapi.downloadReport(docId);

    const rows = parseReturnsFlatFile(rawText);
    console.log(`[sync] Got ${rows.length} return records`);

    for (const row of rows) {
      const orderId = row['order-id'] || row['Order ID'];
      if (!orderId) continue;

      await db.execute({
        sql: `INSERT OR IGNORE INTO returns
                (order_id, return_date, amazon_rma_id, return_tracking, reason_code, refund_amount, updated_at)
              VALUES (?, ?, ?, ?, ?, ?, datetime('now'))`,
        args: [
          orderId,
          row['return-date'] || row['Return Date'],
          row['amazon-rma-id'] || row['Amazon RMA ID'],
          row['tracking-id'] || row['Tracking ID'],
          row['return-reason-code'] || row['Return Reason Code'],
          parseFloat(row['refunded-amount'] || row['Refunded Amount']) || 0,
        ],
      });

      await db.execute({
        sql: `UPDATE orders SET has_return = 1 WHERE order_id = ?`,
        args: [orderId],
      });
    }

    await logSync('returns', 'ok', `Synced ${rows.length} return records`);
    console.log('[sync] Returns sync complete');
  } catch (err) {
    await logSync('returns', 'error', err.message);
    console.error('[sync] Returns sync failed:', err.message);
  }
}

async function syncFbaShipments() {
  await logSync('fba_shipments', 'running', 'Fetching FBA shipments...');
  try {
    console.log('[sync] Fetching FBA inbound shipments...');
    const shipments = await spapi.fetchFbaShipments();
    console.log(`[sync] Got ${shipments.length} FBA shipments`);

    for (const s of shipments) {
      const shipmentId = s.ShipmentId;
      if (!shipmentId) continue;

      // Count total units across all items
      let unitCount = 0;
      try {
        const items = await spapi.fetchFbaShipmentItems(shipmentId);
        unitCount = items.reduce((sum, item) => sum + (parseInt(item.QuantityShipped) || 0), 0);
        await sleep(300);
      } catch (e) {
        console.warn(`[sync] FBA items fetch failed for ${shipmentId}:`, e.message);
      }

      await db.execute({
        sql: `INSERT OR REPLACE INTO fba_shipments
                (shipment_id, shipment_name, destination_fc, shipment_status, unit_count, created_date, synced_at)
              VALUES (?, ?, ?, ?, ?, ?, datetime('now'))`,
        args: [
          shipmentId,
          s.ShipmentName || null,
          s.DestinationFulfillmentCenterId || null,
          s.ShipmentStatus || null,
          unitCount,
          s.CreatedDate || null,
        ],
      });

      await sleep(200);
    }

    await logSync('fba_shipments', 'ok', `Synced ${shipments.length} FBA shipments`);
    console.log('[sync] FBA shipments sync complete');
  } catch (err) {
    await logSync('fba_shipments', 'error', err.message);
    console.error('[sync] FBA shipments sync failed:', err.message);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function startCronJobs() {
  cron.schedule('*/30 * * * *', () => {
    console.log('[cron] Running orders sync...');
    syncOrders();
  });

  cron.schedule('0 */2 * * *', () => {
    console.log('[cron] Running returns sync...');
    syncReturns();
  });

  cron.schedule('0 */4 * * *', () => {
    console.log('[cron] Running FBA shipments sync...');
    syncFbaShipments();
  });

  console.log('[cron] Scheduled: orders every 30min, returns every 2h, FBA every 4h');
}

module.exports = { startCronJobs, syncOrders, syncReturns, syncFbaShipments };
