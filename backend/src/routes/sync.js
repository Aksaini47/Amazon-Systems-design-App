const express = require('express');
const router = express.Router();
const { db } = require('../db/db');
const { syncOrders, syncReturns, syncFbaShipments } = require('../services/sync');

// POST /api/sync/trigger
router.post('/trigger', (req, res) => {
  const { type = 'all' } = req.body;

  res.json({ message: `Sync triggered: ${type}. Running in background.` });

  if (type === 'orders' || type === 'all') syncOrders().catch(console.error);
  if (type === 'returns' || type === 'all') syncReturns().catch(console.error);
  if (type === 'fba' || type === 'all') syncFbaShipments().catch(console.error);
});

// GET /api/sync/status
router.get('/status', async (req, res) => {
  try {
    const result = await db.execute(`
      SELECT job_name, last_run, status, message
      FROM sync_log
      GROUP BY job_name
      HAVING MAX(last_run)
    `);
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
