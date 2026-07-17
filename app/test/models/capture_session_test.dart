import 'package:flutter_test/flutter_test.dart';
import 'package:repairfully_camera/models/capture_session.dart';

void main() {
  group('QCVerdict.triggersClaim', () {
    // Regression for the damagedDifferent bug: 2 of 3 write paths used to
    // hardcode damaged||different and silently wrote claim_trigger: false
    // for the worst-case verdict.
    test('every non-OK verdict triggers a claim', () {
      expect(QCVerdict.ok.triggersClaim, isFalse);
      expect(QCVerdict.damaged.triggersClaim, isTrue);
      expect(QCVerdict.different.triggersClaim, isTrue);
      expect(QCVerdict.damagedDifferent.triggersClaim, isTrue);
    });
  });

  group('CaptureSession.toJson', () {
    CaptureSession session({QCVerdict? verdict}) => CaptureSession(
          orderId: '407-1234567-1234567',
          mode: CaptureMode.rt,
          sessionStartedAt: DateTime(2026, 7, 17),
          verdict: verdict,
        );

    test('claim_trigger true for damagedDifferent', () {
      expect(session(verdict: QCVerdict.damagedDifferent).toJson()['claim_trigger'], isTrue);
    });

    test('claim_trigger false for OK and for no verdict', () {
      expect(session(verdict: QCVerdict.ok).toJson()['claim_trigger'], isFalse);
      expect(session().toJson()['claim_trigger'], isFalse);
    });

    test('app_version comes from the boot-set static, not a hardcoded string', () {
      final prev = CaptureSession.appVersion;
      addTearDown(() => CaptureSession.appVersion = prev);
      CaptureSession.appVersion = '9.9.9+99';
      expect(session().toJson()['app_version'], '9.9.9+99');
    });

    test('verdict serialises by name and is omitted when null', () {
      expect(session(verdict: QCVerdict.damagedDifferent).toJson()['verdict'], 'damagedDifferent');
      expect(session().toJson().containsKey('verdict'), isFalse);
    });
  });

  group('CaptureSession.isPhotoComplete', () {
    CaptureSession pk({String? front, String? back}) => CaptureSession(
          orderId: 'x',
          mode: CaptureMode.pk,
          sessionStartedAt: DateTime(2026),
          frontPhotoPath: front,
          backPhotoPath: back,
        );
    CaptureSession rt(QCVerdict? v,
            {String? front, String? back, String? label, String? contents}) =>
        CaptureSession(
          orderId: 'x',
          mode: CaptureMode.rt,
          sessionStartedAt: DateTime(2026),
          verdict: v,
          frontPhotoPath: front,
          backPhotoPath: back,
          labelPhotoPath: label,
          contentsPhotoPath: contents,
        );

    test('PK needs front + back', () {
      expect(pk().isPhotoComplete, isFalse);
      expect(pk(front: 'f').isPhotoComplete, isFalse);
      expect(pk(front: 'f', back: 'b').isPhotoComplete, isTrue);
    });

    test('RT OK needs front + back only', () {
      expect(rt(QCVerdict.ok, front: 'f', back: 'b').isPhotoComplete, isTrue);
      expect(rt(QCVerdict.ok, front: 'f').isPhotoComplete, isFalse);
    });

    test('RT claim verdicts need label + contents + front + back', () {
      expect(rt(QCVerdict.damagedDifferent, front: 'f', back: 'b').isPhotoComplete, isFalse);
      expect(
        rt(QCVerdict.damagedDifferent, front: 'f', back: 'b', label: 'l', contents: 'c')
            .isPhotoComplete,
        isTrue,
      );
    });
  });
}
