import 'main.dart';

/// Demo-flavor entrypoint. Build with:
///   flutter build apk --flavor demo -t lib/main_demo.dart --release
/// (both flags required — --flavor selects the Gradle/Android side,
/// -t selects this Dart entrypoint; see app/tools/ship_demo.ps1)
Future<void> main() => bootstrap(isDemo: true);
