const express = require('express');
const router = express.Router();
const archiver = require('archiver');
const fs = require('fs');
const path = require('path');
const { db } = require('../db/db');

// GET /api/fba-shipments — list all FBA shipments with video counts
router.get('/', async (req, res) => {
  try {
    const { status, limit = 50, offset = 0 } = req.query;

    let sql = `
      SELECT s.*,
             COUNT(DISTINCT v.id) AS video_count
      FROM fba_shipments s
      LEFT JOIN videos v ON v.fba_shipment_id = s.shipment_id
      WHERE 1=1
    `;
    const args = [];

    if (status) {
      sql += ` AND s.shipment_status = ?`;
      args.push(status);
    }

    sql += ` GROUP BY s.shipment_id ORDER BY s.created_date DESC LIMIT ? OFFSET ?`;
    args.push(parseInt(limit), parseInt(offset));

    const result = await db.execute({ sql, args });

    const countResult = await db.execute({
      sql: `SELECT COUNT(*) as total FROM fba_shipments ${status ? 'WHERE shipment_status = ?' : ''}`,
      args: status ? [status] : [],
    });

    res.json({ shipments: result.rows, total: countResult.rows[0].total });
  } catch (err) {
    console.error('[fba] List error:', err);
    res.status(500).json({ error: err.message });
  }
});

// GET /api/fba-shipments/:shipmentId — single shipment detail with videos
router.get('/:shipmentId', async (req, res) => {
  try {
    const { shipmentId } = req.params;

    const shipResult = await db.execute({
      sql: `SELECT * FROM fba_shipments WHERE shipment_id = ?`,
      args: [shipmentId],
    });
    if (shipResult.rows.length === 0) return res.status(404).json({ error: 'Shipment not found' });

    const videosResult = await db.execute({
      sql: `SELECT * FROM videos WHERE fba_shipment_id = ? ORDER BY fba_box_number ASC, recorded_at ASC`,
      args: [shipmentId],
    });

    res.json({ ...shipResult.rows[0], videos: videosResult.rows });
  } catch (err) {
    console.error('[fba] Detail error:', err);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/fba-shipments — manually add a shipment (no SP-API needed)
router.post('/', async (req, res) => {
  try {
    const { shipment_id, shipment_name, destination_fc, shipment_status = 'WORKING', unit_count = 0 } = req.body;

    if (!shipment_id) return res.status(400).json({ error: 'shipment_id is required' });

    await db.execute({
      sql: `INSERT OR REPLACE INTO fba_shipments
              (shipment_id, shipment_name, destination_fc, shipment_status, unit_count, created_date, synced_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))`,
      args: [shipment_id, shipment_name || null, destination_fc || null, shipment_status, parseInt(unit_count) || 0],
    });

    const result = await db.execute({
      sql: `SELECT * FROM fba_shipments WHERE shipment_id = ?`,
      args: [shipment_id],
    });
    res.json(result.rows[0]);
  } catch (err) {
    console.error('[fba] Create error:', err);
    res.status(500).json({ error: err.message });
  }
});

// GET /api/fba-shipments/:shipmentId/export — download ZIP of all videos for shipment
router.get('/:shipmentId/export', async (req, res) => {
  try {
    const { shipmentId } = req.params;

    const shipResult = await db.execute({
      sql: `SELECT * FROM fba_shipments WHERE shipment_id = ?`,
      args: [shipmentId],
    });
    if (shipResult.rows.length === 0) return res.status(404).json({ error: 'Shipment not found' });

    const videosResult = await db.execute({
      sql: `SELECT * FROM videos WHERE fba_shipment_id = ? ORDER BY fba_box_number ASC`,
      args: [shipmentId],
    });

    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', `attachment; filename="${shipmentId}_evidence.zip"`);

    const archive = archiver('zip', { zlib: { level: 6 } });
    archive.on('error', err => { throw err; });
    archive.pipe(res);

    // Add manifest JSON
    archive.append(JSON.stringify({ shipment: shipResult.rows[0], videos: videosResult.rows }, null, 2), {
      name: 'manifest.json',
    });

    // Add each video file
    const VIDEOS_DIR = path.join(__dirname, '../../videos');
    for (const v of videosResult.rows) {
      const filePath = path.join(VIDEOS_DIR, v.file_name);
      if (fs.existsSync(filePath)) {
        const label = `box${v.fba_box_number || 'X'}_${v.file_name}`;
        archive.file(filePath, { name: label });
      }
    }

    await archive.finalize();
  } catch (err) {
    console.error('[fba] Export error:', err);
    if (!res.headersSent) res.status(500).json({ error: err.message });
  }
});

module.exports = router;
