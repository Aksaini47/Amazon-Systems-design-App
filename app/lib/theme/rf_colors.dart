import 'package:flutter/material.dart';

/// RepairFully Camera App — color tokens (Mahika doctrine, v3.0).
///
/// Authority: `~/.claude/skills/mahika.md §VII "REPAIRFULLY BRAND GUIDELINES"`
/// + Project Bravo's `mahika_capture_specs.md`.
///
/// This is the CAMERA APP palette — seller-facing operational tool, runs on
/// a dark canvas (necessary for video preview contrast + low-light capture
/// + reduced eye strain during long sessions). The customer-facing website
/// uses a separate light-theme palette governed by
/// `06_pipeline/_governance/DESIGN_SYSTEM.txt`. The two palettes share brand
/// navy / coral / success / error tokens but apply them to different
/// surface contexts.
class RfColors {
  RfColors._();

  // ─── BRAND TOKENS (shared with web property) ──────────────────────────
  //
  // Sourced from RepairFully brand lock. Navy is the structural primary;
  // action coral is reserved for commerce / save / primary CTA actions
  // (per W33 lock 10 May 2026 — Etsy-warm `#F1641E`, superseded the older
  // `#F0653E` coral that Mahika v3.0 documents).

  /// Brand primary — structural authority, navy bars, primary surfaces.
  static const navy = Color(0xFF0A1B3F);

  /// Action / commerce / primary CTA. White text site-wide (W33 lock).
  static const action = Color(0xFFF1641E);

  /// PK mode accent — used to color packing-flow UI (capture screen badge,
  /// progress indicators, etc.).
  static const pkAccent = Color(0xFFE86C2B);

  /// RT mode accent — used to color return-flow UI.
  static const rtAccent = Color(0xFF388BFD);

  /// FBA badge / future tier accent (legacy alias retained).
  static const fbaAccent = Color(0xFFF78166);

  // ─── DARK SURFACE TOKENS (camera app — Mahika §VII) ──────────────────
  //
  // GitHub-dark family. Selected for low-light capture sessions where
  // pure-white surfaces would wash out preview contrast.

  /// App background (deepest dark surface).
  static const bg = Color(0xFF0D1117);

  /// Card / panel surface (one elevation above bg).
  static const card = Color(0xFF161B22);

  /// Elevated surface — buttons in rest state, dropdowns, chips.
  static const surface = Color(0xFF21262D);

  /// Standard dark-theme border for cards over `bg`.
  static const border = Color(0xFF30363D);

  /// Subtle separator — for in-card section dividers.
  static const borderSubtle = Color(0xFF21262D);

  // ─── GLASS TOKENS (frosted UI overlays) ───────────────────────────────

  /// Default frosted panel tint over dark mesh.
  static Color glassFill([double opacity = 0.14]) =>
      card.withValues(alpha: opacity);

  /// Elevated glass (app bars, sheets).
  static Color glassElevated([double opacity = 0.22]) =>
      surface.withValues(alpha: opacity);

  /// Glass border highlight.
  static Color glassBorder([double opacity = 0.28]) =>
      Colors.white.withValues(alpha: opacity);

  // ─── TEXT TOKENS ──────────────────────────────────────────────────────

  /// Primary text on dark surfaces.
  static const textPrimary = Color(0xFFE6EDF3);

  /// Secondary text — supporting descriptions, metadata.
  static const textSecondary = Color(0xFF8B949E);

  /// Muted text — timestamps, hints, low-priority labels.
  static const textMuted = Color(0xFF4D5565);

  // ─── STATUS TOKENS ────────────────────────────────────────────────────

  /// Success / connected / completed.
  static const success = Color(0xFF238636);

  /// Success light — checkmarks, success accents.
  static const successLight = Color(0xFF3FB950);

  /// Success tinted bg for confirmation cards.
  static const successBg = Color(0xFF1A3A1A);

  /// Error / form failure / system error.
  static const error = Color(0xFFFF7B72);

  /// Error darker — borders + dark accents.
  static const errorDark = Color(0xFF8B1A1A);

  /// Error tinted bg.
  static const errorBg = Color(0xFF3D1A1A);

  /// Warning / amber alerts (refund-pending day 3+).
  static const warning = Color(0xFFD29922);

  /// Warning tinted bg.
  static const warningBg = Color(0xFF3A2E00);

  /// Information links / secondary actions.
  static const info = Color(0xFF388BFD);

  // ─── LEGACY ALIASES (kept until migration complete) ───────────────────
  @Deprecated('Use RfColors.action')
  static const orange = action;
  @Deprecated('Use RfColors.card')
  static const navyDeep = card;
  static const primary = navy;
  static const successBorder = success;
  static const errorBorder = errorDark;
}

/// Border-radius tokens. Camera app uses 10-12px friendly radii
/// (Mahika §IV — "shape: RoundedRectangleBorder(borderRadius:
/// BorderRadius.circular(10))").
class RfRadius {
  RfRadius._();
  /// Default for buttons + cards.
  static const button = 10.0;
  static const card = 12.0;
  static const chip = 8.0;
  /// Hero blocks / large modals.
  static const lg = 16.0;
  /// Sharp / data block.
  static const precise = 4.0;
}

/// Standard touch-target heights. Mahika §IV "Minimum touch target:
/// 48x48dp (Material guideline)".
class RfButtonHeight {
  RfButtonHeight._();
  static const chip = 36.0;
  static const standard = 48.0;
  static const large = 56.0;
}

/// Animation timings. Mahika §V "200-300ms for micro-interactions,
/// 400ms for page transitions".
class RfDuration {
  RfDuration._();
  static const press = Duration(milliseconds: 200);
  static const fade = Duration(milliseconds: 150);
  static const slide = Duration(milliseconds: 300);
  static const pulse = Duration(milliseconds: 1000);
  static const pageTransition = Duration(milliseconds: 400);
}
