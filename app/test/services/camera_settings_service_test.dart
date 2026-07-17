import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/services/camera_settings_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('aspect picker defaults OFF and round-trips', () async {
    // The capture screen hides the 1:1/3:4/16:9 chip row on this flag —
    // regression for the dead-switch bug where nothing ever read it.
    expect(await CameraSettingsService.getAspectEnabled(), isFalse);
    await CameraSettingsService.setAspectEnabled(true);
    expect(await CameraSettingsService.getAspectEnabled(), isTrue);
  });

  test('claim photo countdown round-trips', () async {
    final initial = await CameraSettingsService.getClaimPhotoCountdown();
    await CameraSettingsService.setClaimPhotoCountdown(!initial);
    expect(await CameraSettingsService.getClaimPhotoCountdown(), !initial);
  });

  test('timestamp watermark flag round-trips', () async {
    final initial = await CameraSettingsService.getTimestampImage();
    await CameraSettingsService.setTimestampImage(!initial);
    expect(await CameraSettingsService.getTimestampImage(), !initial);
  });
}
