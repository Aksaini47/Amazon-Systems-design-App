import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Body for a modal bottom sheet that holds form fields.
///
/// Keeps the content clear of BOTH the keyboard and the system navigation
/// bar (the 3-button or gesture strip), and scrolls when the sheet is taller
/// than the space left — a small phone with the keyboard up, or a long form.
///
/// A sheet that sets only `viewInsets.bottom` (the keyboard) is correct while
/// the keyboard is up and wrong the rest of the time: with the keyboard away
/// that inset is 0 and the bottom buttons sit under the navigation buttons.
/// The bottom inset used here is the larger of the keyboard and the system bar
/// — they overlap (the keyboard covers the bar), so they are not added.
///
/// Open the sheet with `isScrollControlled: true` and `useSafeArea: true` so
/// it also stays below the status bar.
class RfSheetBody extends StatelessWidget {
  final Widget child;

  /// Space around the content, before the system insets are added at the
  /// bottom.
  final EdgeInsets padding;

  const RfSheetBody({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.fromLTRB(20, 20, 20, 16),
  });

  @override
  Widget build(BuildContext context) {
    final mq = MediaQuery.of(context);
    final bottomInset = math.max(mq.viewInsets.bottom, mq.viewPadding.bottom);
    return SingleChildScrollView(
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      padding: padding.copyWith(bottom: padding.bottom + bottomInset),
      child: child,
    );
  }
}
