import 'package:flutter_test/flutter_test.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:repairfully_camera/services/update_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // In tests the Shorebird updater is unavailable, so currentPatchNumber()
  // resolves to null → 0. The build-string path is driven via PackageInfo's
  // mock. That covers the gating logic without a device.
  void mockBuild(String version, String buildNumber) {
    PackageInfo.setMockInitialValues(
      appName: 'RF Logger',
      packageName: 'com.repairfully.logger',
      version: version,
      buildNumber: buildNumber,
      buildSignature: '',
    );
  }

  test('fresh install seeds keys and shows no banner', () async {
    SharedPreferences.setMockInitialValues({});
    mockBuild('2.1.0', '9');
    expect(await UpdateService.consumePendingChangelog(), isNull);
    // Second call after seeding: still nothing (same build, patch 0).
    expect(await UpdateService.consumePendingChangelog(), isNull);
  });

  test('new build shows the changelog exactly once', () async {
    SharedPreferences.setMockInitialValues({
      'shorebird_last_seen_patch_v1': 0,
      'shorebird_last_seen_build_v1': '2.0.0+8',
    });
    mockBuild('2.1.0', '9');
    expect(await UpdateService.consumePendingChangelog(), UpdateService.latestChangelog);
    // Consumed — must not show again on next launch.
    expect(await UpdateService.consumePendingChangelog(), isNull);
  });

  test('same build shows nothing', () async {
    SharedPreferences.setMockInitialValues({
      'shorebird_last_seen_patch_v1': 0,
      'shorebird_last_seen_build_v1': '2.1.0+9',
    });
    mockBuild('2.1.0', '9');
    expect(await UpdateService.consumePendingChangelog(), isNull);
  });

  test('changelog marker matches the pubspec version line format', () {
    // '<release>:<patch> — summary' — ship.ps1 greps this marker.
    expect(
      RegExp(r'^\d+\.\d+\.\d+\+\d+:\d+ ').hasMatch(UpdateService.latestChangelog),
      isTrue,
      reason: 'latestChangelog must start with "<release-version>:<patch-number> "',
    );
  });
}
