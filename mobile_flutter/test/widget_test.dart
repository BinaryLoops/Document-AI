// Basic smoke test: verifies the app boots to the splash screen without
// throwing, and shows the app name.
import 'package:flutter_test/flutter_test.dart';

import 'package:documind_ai/main.dart';
import 'package:documind_ai/core/constants.dart';

void main() {
  testWidgets('App boots and shows splash screen', (WidgetTester tester) async {
    await tester.pumpWidget(const DocuMindApp());
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text(AppConstants.appName), findsOneWidget);
  });
}
