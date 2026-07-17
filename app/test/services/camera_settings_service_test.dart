import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/services/camera_settings_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

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
