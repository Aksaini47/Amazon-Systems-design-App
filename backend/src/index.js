require('dotenv').config();
const express = require('express');
const cors = require('cors');
const os = require('os');
const path = require('path');
const { Bonjour } = require('bonjour-service');
const rateLimit = require('express-rate-limit');
const morgan = require('morgan');

const STORAGE_ROOT = path.resolve(process.env.STORAGE_ROOT || './data');

function getLocalIp() {
  const nets = os.networkInterfaces();
  // Return ALL non-internal IPv4 addresses (covers both WiFi router and
  // phone-hotspot scenarios — usually 192.168.X.X for router and
  // 192.168.43.X / 172.20.X.X for hotspot).
  const addrs = [];
  for (const name of Object.keys(nets)) {
    for (const net of nets[name]) {
      if (net.family === 'IPv4' && !net.internal) addrs.push(net.address);
    }
  }
  return addrs[0] || 'unknown';
}

function getAllLocalIps() {
  const nets = os.networkInterfaces();
  const out = [];
  for (const name of Object.keys(nets)) {
    for (const net of nets[name]) {
      if (net.family === 'IPv4' && !net.internal) {
        out.push({ interface: name, ip: net.address });
      }
    }
  }
  return out;
}

const { initDb } = require('./db/db');
const ordersRouter = require('./routes/orders');
const videosRouter = require('./routes/videos');
const imagesRouter = require('./routes/images');
const returnsRouter = require('./routes/returns');
const syncRouter = require('./routes/sync');
const fbaRouter = require('./routes/fba');
const { startCronJobs } = require('./services/sync');

const app = express();
const PORT = process.env.PORT || 3001;

// General API rate limit — 200 requests/min (plenty for local use)
const generalLimit = rateLimit({
  windowMs: 60 * 1000,
  max: 200,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many requests, slow down.' },
});

// Stricter limit for video uploads — max 30 per 5 minutes
const uploadLimit = rateLimit({
  windowMs: 5 * 60 * 1000,
  max: 30,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Upload rate limit exceeded. Wait a moment before uploading more videos.' },
});

app.use(cors());
app.use(morgan('dev'));
app.use(express.json());
app.use('/api', generalLimit);
app.use('/api/videos/upload', uploadLimit);
app.use('/api/images/upload', uploadLimit);

app.use('/api/orders', ordersRouter);
app.use('/api/videos', videosRouter);
app.use('/api/images', imagesRouter);
app.use('/api/returns', returnsRouter);
app.use('/api/sync', syncRouter);
app.use('/api/fba-shipments', fbaRouter);

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString(), localIp: getLocalIp() });
});

// Surface the current storage root + network info to clients.
// Mobile app uses this to display the upload destination in Settings.
app.get('/api/config', (req, res) => {
  res.json({
    storage_root: STORAGE_ROOT,
    orders_path: path.join(STORAGE_ROOT, 'orders'),
    port: PORT,
    local_ips: getAllLocalIps(),
    hostname: os.hostname(),
  });
});

async function start() {
  await initDb();
  console.log('[db] Database initialized');

  app.listen(PORT, '0.0.0.0', () => {
    const ips = getAllLocalIps();
    console.log(`[server] Running on http://0.0.0.0:${PORT}`);
    console.log(`[server] Local:   http://localhost:${PORT}`);
    for (const { interface: iface, ip } of ips) {
      console.log(`[server] Mobile:  http://${ip}:${PORT}   (${iface})`);
    }
    console.log(`[server] Storage: ${STORAGE_ROOT}`);
    console.log(`[server] Orders:  ${path.join(STORAGE_ROOT, 'orders')}`);

    // Advertise via mDNS so Flutter app can auto-discover on same WiFi
    try {
      const bonjour = new Bonjour();
      bonjour.publish({ name: 'RepairFully', type: 'repairfully', port: Number(PORT) });
      console.log('[mdns] Advertising _repairfully._tcp — mobile app will auto-discover');
    } catch (err) {
      console.warn('[mdns] mDNS advertisement failed (non-fatal):', err.message);
    }

    const hasCredentials = process.env.AMAZON_CLIENT_ID &&
      !process.env.AMAZON_CLIENT_ID.includes('xxxxxxxx');

    if (hasCredentials) {
      startCronJobs();
      console.log('[server] SP-API sync jobs started');
    } else {
      console.log('[server] SP-API credentials not configured — sync skipped');
      console.log('[server] Copy .env.example to .env and fill in your credentials');
    }
  });
}

start().catch(err => {
  console.error('[server] Failed to start:', err);
  process.exit(1);
});

module.exports = app;
