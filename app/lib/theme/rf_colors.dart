import 'package:flutter/material.dart';

/// RepairFully Camera App — color tokens.
///
/// 2026-10-10 revamp (Sir): the app is forced dark and now follows the Claude
/// desktop app's dark look — warm neutral greys (not the old GitHub-dark
/// blue-black), warm off-white text and a terracotta accent. The camera
/// screens keep pure black behind the live preview; everything else sits on
/// these greys. The customer-facing website uses a separate light palette
/// (`06_pipeline/_governance/DESIGN_SYSTEM.txt`).
class RfColors {
  RfColors._();

  // ─── BRAND / ACCENT TOKENS ────────────────────────────────────────────

  /// Brand primary — kept for the legacy [primary] alias only; the revamp no
  /// longer paints anything navy.
  static const navy = Color(0xFF0A1B3F);

  /// Action / primary CTA — terracotta, the Claude desktop accent. White text.
  /// (The launcher icon and native splash keep the older brand orange; those
  /// are native assets and cannot change in an OTA patch.)
  static const action = Color(0xFFD97757);

  /// Pressed / deeper terracotta.
  static const actionDeep = Color(0xFFC6613F);

  /// PK mode accent — packing flow. Soft blue, deep enough for white text.
  static const pkAccent = Color(0xFF4C8BD0);

  /// RT mode accent — return flow. Red-coral: reads as the higher-stakes flow.
  static const rtAccent = Color(0xFFD9534A);

  /// FBA badge / future tier accent (legacy alias retained).
  static const fbaAccent = Color(0xFFF78166);

  // ─── DARK SURFACE TOKENS (warm greys — Claude desktop dark) ───────────

  /// App background.
  static const bg = Color(0xFF262624);

  /// Card / panel surface (one elevation above bg).
  static const card = Color(0xFF30302E);

  /// Elevated surface — dropdowns, menus, sheets, dialogs.
  static const surface = Color(0xFF3A3A37);

  /// Standard border for cards over `bg`.
  static const border = Color(0xFF454540);

  /// Subtle separator — for in-card section dividers.
  static const borderSubtle = Color(0xFF3A3A37);

  // ─── GLASS TOKENS (translucent UI) ────────────────────────────────────

  /// Default translucent panel over the grey background. White-based: a dark
  /// fill is invisible on a dark-grey canvas. Camera chrome that must DARKEN
  /// the video behind it uses an explicit black tint instead.
  static Color glassFill([double opacity = 0.14]) =>
      Colors.white.withValues(alpha: opacity * 0.45);

  /// Elevated glass (app bars, sheets, dialogs).
  static Color glassElevated([double opacity = 0.22]) =>
      surface.withValues(alpha: opacity);

  /// Glass border highlight.
  static Color glassBorder([double opacity = 0.28]) =>
      Colors.white.withValues(alpha: opacity);

  // ─── TEXT TOKENS ──────────────────────────────────────────────────────

  /// Primary text on dark surfaces — warm off-white.
  static const textPrimary = Color(0xFFFAF9F5);

  /// Secondary text — supporting descriptions, metadata.
  static const textSecondary = Color(0xFFB5B3A9);

  /// Muted text — timestamps, hints, low-priority labels.
  static const textMuted = Color(0xFF918F86);

  // ─── STATUS TOKENS ────────────────────────────────────────────────────

  /// Success / connected / completed — sage green.
  static const success = Color(0xFF4F9979);

  /// Success light — checkmarks, success accents.
  static const successLight = Color(0xFF7CC4A1);

  /// Success tinted bg for confirmation cards.
  static const successBg = Color(0xFF22362D);

  /// Error / form failure / system error.
  static const error = Color(0xFFE5675B);

  /// Error darker — borders + dark accents.
  static const errorDark = Color(0xFF8F2F28);

  /// Error tinted bg.
  static const errorBg = Color(0xFF402523);

  /// Warning / amber alerts (refund-pending day 3+).
  static const warning = Color(0xFFE0A24E);

  /// Warning tinted bg.
  static const warningBg = Color(0xFF3D3321);

  /// Information links / secondary actions.
  static const info = Color(0xFF6FA3DC);

  /// Amber highlight — drafts, pending states, soft attention accents.
  static const amber = Color(0xFFE6A55C);

  /// Recording indicator — the universal vivid "REC" red. Deliberately NOT
  /// the softer [error] token: while recording, the dot must be unmissable.
  static const recording = Color(0xFFFF3B30);

  // ─── LEGACY ALIASES (kept until migration complete) ───────────────────
  @Deprecated('Use RfColors.action')
  static const orange = action;
  @Deprecated('Use RfColors.card')
  static const navyDeep = card;
  static const primary = navy;
  static const successBorder = success;
  static const errorBorder = errorDark;
}

/// Border-radius tokens.
class RfRadius {
  RfRadius._();
  /// Default for rectangular buttons (legacy) + small cards.
  static const button = 10.0;
  static const card = 12.0;
  static const chip = 8.0;
  /// Hero blocks / large modals.
  static const lg = 16.0;
  /// Sharp / data block.
  static const precise = 4.0;
  /// Fully-rounded pill/capsule — every button, chip and round control.
  static const pill = 999.0;
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
  static const controlsFade = Duration(milliseconds: 250);
  static const slide = Duration(milliseconds: 300);
  static const pulse = Duration(milliseconds: 1000);
  static const pageTransition = Duration(milliseconds: 400);

  /// Standard curves — enter decelerates, exit accelerates, press eases out.
  static const enter = Curves.easeOutCubic;
  static const exit = Curves.easeInCubic;
  static const pressCurve = Curves.easeOut;
}

/// Spacing scale — 4pt grid. Use these instead of ad-hoc EdgeInsets values
/// when writing NEW layout code; existing screens migrate opportunistically.
class RfSpace {
  RfSpace._();
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 16.0;
  static const xl = 20.0;
  static const xxl = 24.0;
}

/// Type scale — sizes/weights the screens already converge on, named.
/// Wired into ThemeData.textTheme (rf_theme.dart) so unstyled Text inherits it.
class RfType {
  RfType._();
  static const title = TextStyle(color: RfColors.textPrimary, fontSize: 20, fontWeight: FontWeight.bold);
  static const heading = TextStyle(color: RfColors.textPrimary, fontSize: 17, fontWeight: FontWeight.bold);
  static const label = TextStyle(color: RfColors.textPrimary, fontSize: 14, fontWeight: FontWeight.w600);
  static const body = TextStyle(color: RfColors.textPrimary, fontSize: 14);
  static const caption = TextStyle(color: RfColors.textSecondary, fontSize: 12, height: 1.3);
  static const mono = TextStyle(color: RfColors.textPrimary, fontSize: 12, fontFamily: 'monospace');
}
