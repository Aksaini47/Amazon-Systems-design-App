/// Flavor flag set once at boot by main.dart (prod) / main_demo.dart (demo).
/// Read anywhere in the app instead of threading a flavor param through
/// every call site — see main.dart's bootstrap() for where this is set.
class AppConfig {
  AppConfig._();

  static bool isDemo = false;
}
