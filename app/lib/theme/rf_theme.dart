import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'rf_colors.dart';

/// Status/navigation bar styling for the dark-grey canvas: transparent status
/// bar with light icons, navigation bar in the app background colour.
const SystemUiOverlayStyle rfSystemUiStyle = SystemUiOverlayStyle(
  statusBarColor: Colors.transparent,
  statusBarIconBrightness: Brightness.light,
  statusBarBrightness: Brightness.dark,
  systemNavigationBarColor: RfColors.bg,
  systemNavigationBarIconBrightness: Brightness.light,
  systemNavigationBarDividerColor: Colors.transparent,
);

/// The one app theme. Dark only (2026-10-10, Sir): a warm dark-grey canvas in
/// the style of the Claude desktop app, terracotta primary, and component
/// themes for every raw Material widget the screens still use (Switch,
/// SnackBar, TabBar, popup menu, pickers...) so those match without
/// per-call-site styling.
ThemeData buildRfTheme() {
  const scheme = ColorScheme(
    brightness: Brightness.dark,
    primary: RfColors.action,
    onPrimary: Colors.white,
    primaryContainer: RfColors.actionDeep,
    onPrimaryContainer: Colors.white,
    secondary: RfColors.pkAccent,
    onSecondary: Colors.white,
    tertiary: RfColors.successLight,
    onTertiary: RfColors.bg,
    error: RfColors.error,
    onError: Colors.white,
    surface: RfColors.card,
    onSurface: RfColors.textPrimary,
    onSurfaceVariant: RfColors.textSecondary,
    outline: RfColors.border,
    outlineVariant: RfColors.borderSubtle,
    surfaceContainerHighest: RfColors.surface,
    surfaceTint: Colors.transparent,
    shadow: Colors.black,
  );

  final hairline = Colors.white.withValues(alpha: 0.10);

  return ThemeData(
    colorScheme: scheme,
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: RfColors.bg,
    canvasColor: RfColors.bg,
    splashColor: Colors.white.withValues(alpha: 0.06),
    highlightColor: Colors.white.withValues(alpha: 0.04),
    textTheme: const TextTheme(
      titleLarge: RfType.title,
      titleMedium: RfType.heading,
      labelLarge: RfType.label,
      bodyMedium: RfType.body,
      bodySmall: RfType.caption,
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: RfColors.glassElevated(0.94),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RfRadius.lg),
        side: BorderSide(color: hairline),
      ),
      // Safety net for any dialog that forgets its own title/content colors.
      titleTextStyle: const TextStyle(color: RfColors.textPrimary, fontSize: 18, fontWeight: FontWeight.w700),
      contentTextStyle: const TextStyle(color: RfColors.textSecondary, fontSize: 14),
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: RfColors.surface,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RfRadius.card + 2),
        side: BorderSide(color: hairline),
      ),
      contentTextStyle: const TextStyle(color: RfColors.textPrimary, fontSize: 14),
      actionTextColor: RfColors.action,
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: RfColors.glassElevated(0.96),
      modalBackgroundColor: RfColors.glassElevated(0.96),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(RfRadius.lg)),
      ),
    ),
    cardTheme: CardThemeData(
      color: RfColors.glassFill(0.16),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RfRadius.card),
        side: BorderSide(color: hairline),
      ),
    ),
    dividerTheme: DividerThemeData(color: Colors.white.withValues(alpha: 0.08), thickness: 1),
    appBarTheme: AppBarTheme(
      backgroundColor: Colors.transparent,
      foregroundColor: RfColors.textPrimary,
      elevation: 0,
      scrolledUnderElevation: 0,
      systemOverlayStyle: rfSystemUiStyle,
      shape: Border(bottom: BorderSide(color: Colors.white.withValues(alpha: 0.08))),
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.all(Colors.white),
      trackColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.selected)
            ? RfColors.success
            : Colors.white.withValues(alpha: 0.16),
      ),
      trackOutlineColor: WidgetStateProperty.all(Colors.transparent),
    ),
    tabBarTheme: const TabBarThemeData(
      indicatorColor: RfColors.action,
      labelColor: RfColors.textPrimary,
      unselectedLabelColor: RfColors.textSecondary,
      dividerColor: Colors.transparent,
    ),
    popupMenuTheme: PopupMenuThemeData(
      color: RfColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RfRadius.card + 2),
        side: BorderSide(color: hairline),
      ),
      textStyle: const TextStyle(color: RfColors.textPrimary, fontSize: 14),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: RfColors.action,
      linearTrackColor: Colors.white.withValues(alpha: 0.12),
    ),
    textSelectionTheme: TextSelectionThemeData(
      cursorColor: RfColors.action,
      selectionColor: RfColors.action.withValues(alpha: 0.35),
      selectionHandleColor: RfColors.action,
    ),
    inputDecorationTheme: InputDecorationTheme(
      hintStyle: const TextStyle(color: RfColors.textMuted),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(RfRadius.card),
        borderSide: const BorderSide(color: RfColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(RfRadius.card),
        borderSide: const BorderSide(color: RfColors.action, width: 1.5),
      ),
    ),
    tooltipTheme: TooltipThemeData(
      decoration: BoxDecoration(
        color: RfColors.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: hairline),
      ),
      textStyle: const TextStyle(color: RfColors.textPrimary, fontSize: 12),
    ),
    scrollbarTheme: ScrollbarThemeData(
      thumbColor: WidgetStateProperty.all(Colors.white.withValues(alpha: 0.25)),
    ),
    datePickerTheme: const DatePickerThemeData(backgroundColor: RfColors.surface),
    timePickerTheme: const TimePickerThemeData(backgroundColor: RfColors.surface),
  );
}
