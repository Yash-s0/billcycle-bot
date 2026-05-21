import 'package:flutter/material.dart';

import 'core/routing/app_router.dart';
import 'core/theme/app_theme.dart';

class BillCycleApp extends StatelessWidget {
  const BillCycleApp({super.key});

  @override
  Widget build(BuildContext context) {
    final router = createRouter();
    return MaterialApp.router(
      title: 'BillCycle',
      theme: AppTheme.dark(),
      debugShowCheckedModeBanner: false,
      routerConfig: router,
    );
  }
}
