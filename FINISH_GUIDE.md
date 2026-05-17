# RepairFully Camera App — Project Handover Guide

This document provides everything you need to maintain and run the RepairFully system.

## 🚀 Quick Start (Local Development)

### 1. Backend
- **Path**: `D:\Antigravity\RepairFully Camera App Project\backend`
- **Setup**: `npm install`
- **Run**: `npm run dev`
- **Note**: Ensure `.env` has valid Amazon SP-API credentials.

### 2. Dashboard
- **Path**: `D:\Antigravity\RepairFully Camera App Project\dashboard`
- **Setup**: `npm install`
- **Run**: `npm run dev`
- **Access**: `http://localhost:3000`

### 3. Mobile
- **Path**: `D:\Antigravity\RepairFully Camera App Project\mobile`
- **Setup**: `flutter pub get`
- **Run**: `flutter run`
- **Features**: Auto-discovery of backend, video compression (720p), retries.

---

## 🛠️ Key Technical Features

### Video Pipeline
- **Mobile**: Recordings are compressed to **720p** using the `video_compress` package before upload.
- **Backend Validation**: The backend strictly validates `order_id` or `fba_shipment_id` against the database. It will **reject** uploads for non-existent orders to prevent data clutter.
- **Streaming**: The dashboard streams videos using range requests, allowing you to seek through large files instantly.

### Amazon Sync
- **Real-time Status**: The Dashboard NavBar features a live **Sync Indicator**. It pulses blue when Amazon is being polled.
- **Auto-Sync**: The backend runs cron jobs:
  - Orders: Every 30 minutes
  - Returns: Every 2 hours
  - FBA Shipments: Every 4 hours

### Evidence Management
- **Image Gallery**: Order details show a grid of captured evidence photos.
- **Claim Helper**: A built-in modal provides one-click copy of Order IDs and quick access to both Packing and Unpacking videos for safe-t/A-to-Z claims.

---

## 💾 Infrastructure (D: Drive Safety)
All tooling is configured to keep your `C:` drive clean:
- **Android SDK**: `D:\Antigravity\Android\Sdk`
- **Gradle Cache**: `D:\Antigravity\.gradle`
- **AVDs**: `D:\Antigravity\.android`
- **Project Data**: All SQLite databases (`.db`), videos, and images are stored in the project folder on `D:`.

---

## ✅ Project Completion Status
- [x] Full-stack architecture (Backend, Frontend, Mobile)
- [x] SP-API Integration (Orders, Returns, FBA)
- [x] mDNS Service Discovery
- [x] 720p Video Compression & Retry Logic
- [x] Real-time Sync UI
- [x] Secure upload validation
- [x] isolated D: drive environment

**Project is now ready for production use and device testing.**
