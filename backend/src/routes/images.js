const express = require('express');
const router = express.Router();
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const { db } = require('../db/db');

// Photos land in STORAGE_ROOT/orders/{order_id}/ alongside the video.
// Same root as videos.js — configured via STORAGE_ROOT env.
const STORAGE_ROOT = path.resolve(
  process.env.STORAGE_ROOT ||
  process.env.IMAGES_DIR?.replace(/[\\/]images[\\/]?$/, '') ||
  './data'
);
fs.mkdirSync(path.join(STORAGE_ROOT, 'orders'), { recursive: true });

function safeId(id) {
  return String(id || 'unknown').replace(/[^\w\-.]/g, '_');
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const id = req.body.order_id || 'unknown';
    const dir = path.join(STORAGE_ROOT, 'orders', safeId(id));
    fs.mkdirSync(dir, { recursive: true });
    cb(null, dir);
  },
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname) || '.jpg';
    const id = safeId(req.body.order_id || 'unknown');
    // Preserve original filename (it carries side info: front/back/label etc.)
    // but prepend order id for clarity if not already there.
    const orig = path.basename(file.originalname, ext);
    const name = orig.startsWith(id) ? orig : `${id}_${orig}`;
    cb(null, `${name}${ext}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: 20 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    const allowed = ['.jpg', '.jpeg', '.png', '.webp', '.heic'];
    const ext = path.extname(file.originalname).toLowerCase();
    if (allowed.includes(ext)) cb(null, true);
    else cb(new Error(`Invalid file type: ${ext}`));
  },
});

// POST /api/images/upload
router.post('/upload', upload.single('image'), async (req, res) => {
  try {
    const { order_id, captured_at } = req.body;

    if (!req.file) return res.status(400).json({ error: 'No image file provided' });
    if (!order_id) return res.status(400).json({ error: 'order_id is required' });

    const orderCheck = await db.execute({
      sql: `SELECT 1 FROM orders WHERE order_id = ?`,
      args: [order_id]
    });
    if (orderCheck.rows.length === 0) {
      if (req.file) fs.unlinkSync(req.file.path);
      return res.status(404).json({ error: `Order ID ${order_id} not found. Please sync first.` });
    }

    const result = await db.execute({
      sql: `INSERT INTO images (order_id, file_path, file_name, captured_at) VALUES (?, ?, ?, ?)`,
      args: [order_id, req.file.path, req.file.filename, captured_at || new Date().toISOString()],
    });

    res.json({
      id: Number(result.lastInsertRowid),
      file_name: req.file.filename,
      message: 'Image uploaded successfully',
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/images/:id — serve image file
router.get('/:id', async (req, res) => {
  try {
    const result = await db.execute({
      sql: `SELECT * FROM images WHERE id = ?`,
      args: [req.params.id],
    });
    const image = result.rows[0];
    if (!image) return res.status(404).json({ error: 'Image not found' });
    if (!fs.existsSync(image.file_path)) return res.status(404).json({ error: 'Image file missing' });

    res.sendFile(path.resolve(image.file_path));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
