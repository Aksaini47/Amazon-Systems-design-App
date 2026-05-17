const express = require('express');
const router = express.Router();
const fs = require('fs');
const archiver = require('archiver');
const { db } = require('../db/db');

// GET /api/orders — list orders with optional search/filter
router.get('/', async (req, res) => {
  try {
    const { search, status, has_return, limit = 50, offset = 0 } = req.query;

    let sql = `SELECT * FROM orders WHERE 1=1`;
    const args = [];

    if (search) {
      sql += ` AND (order_id LIKE ? OR product_title LIKE ? OR sku LIKE ?)`;
      const like = `%${search}%`;
      args.push(like, like, like);
    }
    if (status) {
      sql += ` AND order_status = ?`;
      args.push(status);
    }
    if (has_return === 'true' || has_return === '1') {
      sql += ` AND has_return = 1`;
    }

    sql += ` ORDER BY purchase_date DESC LIMIT ? OFFSET ?`;
    args.push(parseInt(limit), parseInt(offset));

    const [ordersRes, totalRes] = await Promise.all([
      db.execute({ sql, args }),
      db.execute(`SELECT COUNT(*) as count FROM orders`),
    ]);

    res.json({
      orders: ordersRes.rows,
      total: totalRes.rows[0]?.count ?? 0,
      limit: parseInt(limit),
      offset: parseInt(offset),
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/orders/by-awb/:awb — lookup order by AWB barcode
router.get('/by-awb/:awb', async (req, res) => {
  try {
    const result = await db.execute({
      sql: `SELECT awb_mappings.awb_number, awb_mappings.carrier, awb_mappings.package_status,
                   orders.*
            FROM awb_mappings
            JOIN orders ON awb_mappings.order_id = orders.order_id
            WHERE awb_mappings.awb_number = ?`,
      args: [req.params.awb],
    });

    if (!result.rows[0]) {
      return res.status(404).json({ error: 'AWB not found', awb: req.params.awb });
    }
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/orders/:orderId — single order detail with videos, images, returns, AWBs
router.get('/:orderId', async (req, res) => {
  try {
    const [orderRes, videosRes, imagesRes, returnsRes, awbsRes] = await Promise.all([
      db.execute({ sql: `SELECT * FROM orders WHERE order_id = ?`, args: [req.params.orderId] }),
      db.execute({ sql: `SELECT * FROM videos WHERE order_id = ? ORDER BY uploaded_at ASC`, args: [req.params.orderId] }),
      db.execute({ sql: `SELECT * FROM images WHERE order_id = ? ORDER BY captured_at ASC`, args: [req.params.orderId] }),
      db.execute({ sql: `SELECT * FROM returns WHERE order_id = ?`, args: [req.params.orderId] }),
      db.execute({ sql: `SELECT awb_number, carrier FROM awb_mappings WHERE order_id = ?`, args: [req.params.orderId] }),
    ]);

    const order = orderRes.rows[0];
    if (!order) return res.status(404).json({ error: 'Order not found' });

    res.json({
      ...order,
      videos: videosRes.rows,
      images: imagesRes.rows,
      returns: returnsRes.rows,
      awbs: awbsRes.rows,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/orders — manually create or update an order
router.post('/', async (req, res) => {
  try {
    const {
      order_id, product_title, purchase_date, order_status = 'Shipped',
      fulfillment_channel = 'MFN', asin, sku, quantity = 1,
      awb_number, carrier,
    } = req.body;

    if (!order_id) return res.status(400).json({ error: 'order_id is required' });

    const orderIdPattern = /^\d{3}-\d{7}-\d{7}$/;
    if (!orderIdPattern.test(order_id)) {
      return res.status(400).json({ error: 'order_id must be in format 403-1234567-1234567' });
    }

    await db.execute({
      sql: `INSERT INTO orders (order_id, product_title, purchase_date, order_status, fulfillment_channel, asin, sku, quantity, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(order_id) DO UPDATE SET
              product_title       = excluded.product_title,
              order_status        = excluded.order_status,
              fulfillment_channel = excluded.fulfillment_channel,
              asin                = excluded.asin,
              sku                 = excluded.sku,
              quantity            = excluded.quantity,
              synced_at           = datetime('now')`,
      args: [
        order_id, product_title || null,
        purchase_date || new Date().toISOString(),
        order_status, fulfillment_channel,
        asin || null, sku || null, parseInt(quantity) || 1,
      ],
    });

    if (awb_number) {
      await db.execute({
        sql: `INSERT INTO awb_mappings (awb_number, order_id, carrier)
              VALUES (?, ?, ?)
              ON CONFLICT(awb_number) DO UPDATE SET order_id = excluded.order_id, carrier = excluded.carrier`,
        args: [awb_number, order_id, carrier || null],
      });
    }

    res.json({ message: 'Order saved', order_id });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/orders/:orderId/videos
router.get('/:orderId/videos', async (req, res) => {
  try {
    const result = await db.execute({
      sql: `SELECT * FROM videos WHERE order_id = ? ORDER BY uploaded_at ASC`,
      args: [req.params.orderId],
    });
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/orders/:orderId/returns
router.get('/:orderId/returns', async (req, res) => {
  try {
    const result = await db.execute({
      sql: `SELECT * FROM returns WHERE order_id = ?`,
      args: [req.params.orderId],
    });
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/orders/:orderId/export — download ZIP of all evidence
router.get('/:orderId/export', async (req, res) => {
  try {
    const orderId = req.params.orderId;

    const [orderRes, videosRes, imagesRes, returnsRes] = await Promise.all([
      db.execute({ sql: `SELECT * FROM orders WHERE order_id = ?`, args: [orderId] }),
      db.execute({ sql: `SELECT * FROM videos WHERE order_id = ?`, args: [orderId] }),
      db.execute({ sql: `SELECT * FROM images WHERE order_id = ?`, args: [orderId] }),
      db.execute({ sql: `SELECT * FROM returns WHERE order_id = ?`, args: [orderId] }),
    ]);

    const order = orderRes.rows[0];
    if (!order) return res.status(404).json({ error: 'Order not found' });

    const safeId = orderId.replace(/-/g, '_');
    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', `attachment; filename="evidence_${safeId}.zip"`);

    const archive = archiver('zip', { zlib: { level: 6 } });
    archive.on('error', err => { throw err; });
    archive.pipe(res);

    // order_info.json
    const info = {
      order_id: order.order_id,
      product_title: order.product_title,
      purchase_date: order.purchase_date,
      order_status: order.order_status,
      fulfillment_channel: order.fulfillment_channel,
      asin: order.asin,
      sku: order.sku,
      quantity: order.quantity,
      videos: videosRes.rows.map(v => ({
        type: v.type,
        file_name: v.file_name,
        duration_seconds: v.duration_seconds,
        recorded_at: v.recorded_at,
      })),
      images: imagesRes.rows.map(i => ({ file_name: i.file_name, captured_at: i.captured_at })),
      returns: returnsRes.rows,
      exported_at: new Date().toISOString(),
    };
    archive.append(JSON.stringify(info, null, 2), { name: 'order_info.json' });

    // Videos
    for (const video of videosRes.rows) {
      if (video.file_path && fs.existsSync(video.file_path)) {
        archive.file(video.file_path, { name: `videos/${video.file_name}` });
      }
    }

    // Images
    for (const image of imagesRes.rows) {
      if (image.file_path && fs.existsSync(image.file_path)) {
        archive.file(image.file_path, { name: `images/${image.file_name}` });
      }
    }

    await archive.finalize();
  } catch (err) {
    if (!res.headersSent) res.status(500).json({ error: err.message });
  }
});

module.exports = router;
