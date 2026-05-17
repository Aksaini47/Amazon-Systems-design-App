const express = require('express');
const router = express.Router();
const { db } = require('../db/db');

// GET /api/returns
router.get('/', async (req, res) => {
  try {
    const { claim_status, limit = 50, offset = 0 } = req.query;

    let sql = `
      SELECT returns.*, orders.product_title, orders.asin, orders.sku
      FROM returns
      LEFT JOIN orders ON returns.order_id = orders.order_id
      WHERE 1=1
    `;
    const args = [];

    if (claim_status) {
      sql += ` AND returns.claim_status = ?`;
      args.push(claim_status);
    }

    sql += ` ORDER BY returns.return_date DESC LIMIT ? OFFSET ?`;
    args.push(parseInt(limit), parseInt(offset));

    const [returnsRes, totalRes] = await Promise.all([
      db.execute({ sql, args }),
      db.execute(`SELECT COUNT(*) as count FROM returns`),
    ]);

    res.json({ returns: returnsRes.rows, total: totalRes.rows[0]?.count ?? 0 });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// PATCH /api/returns/:id/claim-status
router.patch('/:id/claim-status', async (req, res) => {
  try {
    const { claim_status } = req.body;
    const valid = ['none', 'pending', 'filed', 'resolved'];

    if (!valid.includes(claim_status)) {
      return res.status(400).json({ error: `claim_status must be one of: ${valid.join(', ')}` });
    }

    const result = await db.execute({
      sql: `UPDATE returns SET claim_status = ?, updated_at = datetime('now') WHERE id = ?`,
      args: [claim_status, req.params.id],
    });

    if (result.rowsAffected === 0) return res.status(404).json({ error: 'Return not found' });

    res.json({ message: 'Claim status updated', claim_status });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
