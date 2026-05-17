const express = require('express');
const router = express.Router();
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const { db } = require('../db/db');

// All session files (video + photos + meta.json) land under
// STORAGE_ROOT/orders/{order_id}/ — same layout the mobile app uses for its
// local copy. Configure via STORAGE_ROOT in .env (e.g., D:/RepairFullyData).
// Falls back to legacy VIDEOS_DIR for backward compat with old installs.
const STORAGE_ROOT = path.resolve(
  process.env.STORAGE_ROOT ||
  process.env.VIDEOS_DIR?.replace(/[\\/]videos[\\/]?$/, '') ||
  './data'
);
fs.mkdirSync(path.join(STORAGE_ROOT, 'orders'), { recursive: true });

// Sanitize an order ID so it's safe as a folder name
function safeId(id) {
  return String(id || 'unknown').replace(/[^\w\-.]/g, '_');
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const id = req.body.order_id || req.body.fba_shipment_id || 'unknown';
    const dir = path.join(STORAGE_ROOT, 'orders', safeId(id));
    fs.mkdirSync(dir, { recursive: true });
    cb(null, dir);
  },
  filename: (req, file, cb) => {
    const type = req.body.type || 'packing';
    const ext = path.extname(file.originalname) || '.mp4';
    // Match mobile-app convention: {orderId}_{PK|RT}.mp4
    const id = safeId(req.body.order_id || req.body.fba_shipment_id || 'unknown');
    const tag = type === 'packing' ? 'PK' : 'RT';
    cb(null, `${id}_${tag}${ext}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: 500 * 1024 * 1024 }, // 500MB max
  fileFilter: (req, file, cb) => {
    const allowed = ['.mp4', '.mov', '.avi', '.mkv', '.webm'];
    const ext = path.extname(file.originalname).toLowerCase();
    if (allowed.includes(ext)) cb(null, true);
    else cb(new Error(`Invalid file type: ${ext}`));
  },
});

// GET /api/videos — list all videos, newest first
router.get('/', async (req, res) => {
  try {
    const limit = Math.min(parseInt(req.query.limit || '100'), 500);
    const offset = parseInt(req.query.offset || '0');

    const result = await db.execute({
      sql: `SELECT id, order_id, fba_shipment_id, fba_box_number, type,
                   file_name, duration_seconds, file_size_bytes, recorded_at, uploaded_at
            FROM videos
            ORDER BY uploaded_at DESC
            LIMIT ? OFFSET ?`,
      args: [limit, offset],
    });

    const countResult = await db.execute(`SELECT COUNT(*) as total FROM videos`);

    res.json({
      videos: result.rows,
      total: Number(countResult.rows[0].total),
      limit,
      offset,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/videos/upload
// Accepts either order_id (FBM) or fba_shipment_id + fba_box_number (FBA)
router.post('/upload', upload.single('video'), async (req, res) => {

  try {
    const { order_id, fba_shipment_id, fba_box_number, type, recorded_at, duration_seconds } = req.body;

    if (!req.file) return res.status(400).json({ error: 'No video file provided' });
    if (!order_id && !fba_shipment_id) {
      return res.status(400).json({ error: 'order_id or fba_shipment_id is required' });
    }

    if (order_id) {
      const orderCheck = await db.execute({
        sql: `SELECT 1 FROM orders WHERE order_id = ?`,
        args: [order_id]
      });
      if (orderCheck.rows.length === 0) {
        if (req.file) fs.unlinkSync(req.file.path);
        return res.status(404).json({ error: `Order ID ${order_id} not found in database. Please sync first.` });
      }
    }

    if (fba_shipment_id) {
      const fbaCheck = await db.execute({
        sql: `SELECT 1 FROM fba_shipments WHERE shipment_id = ?`,
        args: [fba_shipment_id]
      });
      if (fbaCheck.rows.length === 0) {
        if (req.file) fs.unlinkSync(req.file.path);
        return res.status(404).json({ error: `FBA Shipment ID ${fba_shipment_id} not found in database.` });
      }
    }

    if (!['packing', 'unpacking'].includes(type)) {
      return res.status(400).json({ error: 'type must be packing or unpacking' });
    }

    const result = await db.execute({
      sql: `INSERT INTO videos
              (order_id, fba_shipment_id, fba_box_number, type, file_path, file_name, duration_seconds, file_size_bytes, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      args: [
        order_id || null,
        fba_shipment_id || null,
        fba_box_number ? parseInt(fba_box_number) : null,
        type,
        req.file.path,
        req.file.filename,
        parseFloat(duration_seconds) || null,
        req.file.size,
        recorded_at || new Date().toISOString(),
      ],
    });

    res.json({
      id: Number(result.lastInsertRowid),
      file_name: req.file.filename,
      file_size_bytes: req.file.size,
      message: 'Video uploaded successfully',
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/videos/:id/stream — stream video to browser with range support
router.get('/:id/stream', async (req, res) => {
  try {
    const result = await db.execute({
      sql: `SELECT * FROM videos WHERE id = ?`,
      args: [req.params.id],
    });
    const video = result.rows[0];
    if (!video) return res.status(404).json({ error: 'Video not found' });

    const filePath = video.file_path;
    if (!fs.existsSync(filePath)) return res.status(404).json({ error: 'Video file missing on disk' });

    const stat = fs.statSync(filePath);
    const fileSize = stat.size;
    const range = req.headers.range;

    if (range) {
      const parts = range.replace(/bytes=/, '').split('-');
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
      const chunkSize = end - start + 1;

      res.writeHead(206, {
        'Content-Range': `bytes ${start}-${end}/${fileSize}`,
        'Accept-Ranges': 'bytes',
        'Content-Length': chunkSize,
        'Content-Type': 'video/mp4',
      });
      fs.createReadStream(filePath, { start, end }).pipe(res);
    } else {
      res.writeHead(200, {
        'Content-Length': fileSize,
        'Content-Type': 'video/mp4',
        'Accept-Ranges': 'bytes',
      });
      fs.createReadStream(filePath).pipe(res);
    }
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// DELETE /api/videos/:id
router.delete('/:id', async (req, res) => {
  try {
    const result = await db.execute({
      sql: `SELECT * FROM videos WHERE id = ?`,
      args: [req.params.id],
    });
    const video = result.rows[0];
    if (!video) return res.status(404).json({ error: 'Video not found' });

    if (fs.existsSync(video.file_path)) fs.unlinkSync(video.file_path);

    await db.execute({ sql: `DELETE FROM videos WHERE id = ?`, args: [req.params.id] });
    res.json({ message: 'Video deleted' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
