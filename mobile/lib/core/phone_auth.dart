import 'package:firebase_auth/firebase_auth.dart';

abstract class PhoneIdentityProvider {
  Future<void> sendCode(
    String phone, {
    required void Function(String verificationId) onCodeSent,
    required Future<void> Function(String idToken) onVerified,
    required void Function(String message) onError,
  });

  Future<String> confirmCode(String verificationId, String code);
  Future<void> signOut();
}

class FirebasePhoneIdentity implements PhoneIdentityProvider {
  FirebasePhoneIdentity([FirebaseAuth? auth]) : _auth = auth ?? FirebaseAuth.instance;

  final FirebaseAuth _auth;

  Future<String> _token(PhoneAuthCredential credential) async {
    final user = (await _auth.signInWithCredential(credential)).user;
    final token = await user?.getIdToken();
    if (token == null || token.isEmpty) {
      throw StateError('Phone verification returned no identity token.');
    }
    return token;
  }

  @override
  Future<void> sendCode(
    String phone, {
    required void Function(String verificationId) onCodeSent,
    required Future<void> Function(String idToken) onVerified,
    required void Function(String message) onError,
  }) =>
      _auth.verifyPhoneNumber(
        phoneNumber: phone,
        verificationCompleted: (credential) async {
          try {
            await onVerified(await _token(credential));
          } catch (_) {
            onError('Phone sign-in could not finish. Please retry.');
          }
        },
        verificationFailed: (error) => onError(error.message ?? 'Phone verification failed.'),
        codeSent: (verificationId, _) => onCodeSent(verificationId),
        codeAutoRetrievalTimeout: (_) {},
      );

  @override
  Future<String> confirmCode(String verificationId, String code) => _token(
        PhoneAuthProvider.credential(verificationId: verificationId, smsCode: code),
      );

  @override
  Future<void> signOut() => _auth.signOut();
}
