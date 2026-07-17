import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/models/capture_session.dart';
import 'package:repairfully_camera/services/file_naming_service.dart';

void main() {
  const id = '407-1234567-1234567';

  test('file names carry order id, mode, and side', () {
    expect(FileNamingService.videoFileName(id, CaptureMode.pk), '${id}_PK.mp4');
    expect(
      FileNamingService.photoFileName(id, CaptureMode.rt, PhotoSide.label),
      '${id}_RT_label.jpg',
    );
    expect(FileNamingService.metaFileName(id), '${id}_meta.json');
  });

  test('folder name gets the mode suffix so PK and RT never collide', () {
    expect(FileNamingService.orderFolderName(id, CaptureMode.pk), '$id-PK');
    expect(FileNamingService.orderFolderName(id, CaptureMode.rt), '$id-RT');
  });

  test('unsafe characters are sanitised in folder names', () {
    expect(
      FileNamingService.orderFolderName('407/12*34', CaptureMode.pk),
      '407_12_34-PK',
    );
  });

  test('folder key round-trips back to bare id + mode', () {
    final folder = FileNamingService.orderFolderName(id, CaptureMode.rt);
    expect(FileNamingService.bareOrderIdFromFolder(folder), id);
    expect(FileNamingService.modeFromFolder(folder), CaptureMode.rt);
  });

  test('unsuffixed folder returns null mode and unchanged id', () {
    expect(FileNamingService.modeFromFolder(id), isNull);
    expect(FileNamingService.bareOrderIdFromFolder(id), id);
  });
}
