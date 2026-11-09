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

  group('default label scanner (Sir, 2026-11-09)', () {
    test('is the barcode reader until Sir changes it', () async {
      expect(await CameraSettingsService.getDefaultScanMethod(), LabelScanMethod.barcode);
    });

    test('round-trips both ways', () async {
      await CameraSettingsService.setDefaultScanMethod(LabelScanMethod.text);
      expect(await CameraSettingsService.getDefaultScanMethod(), LabelScanMethod.text);
      await CameraSettingsService.setDefaultScanMethod(LabelScanMethod.barcode);
      expect(await CameraSettingsService.getDefaultScanMethod(), LabelScanMethod.barcode);
    });

    test('an unknown stored value falls back to barcode', () async {
      SharedPreferences.setMockInitialValues({'default_scan_method': 'something_else'});
      expect(await CameraSettingsService.getDefaultScanMethod(), LabelScanMethod.barcode);
    });

    test('restore defaults puts it back to barcode', () async {
      await CameraSettingsService.setDefaultScanMethod(LabelScanMethod.text);
      await CameraSettingsService.restoreDefaults();
      expect(await CameraSettingsService.getDefaultScanMethod(), LabelScanMethod.barcode);
    });
  });

  test('timestamp watermark flag round-trips', () async {
    final initial = await CameraSettingsService.getTimestampImage();
    await CameraSettingsService.setTimestampImage(!initial);
    expect(await CameraSettingsService.getTimestampImage(), !initial);
  });
}
