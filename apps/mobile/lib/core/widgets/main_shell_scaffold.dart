import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class MainShellScaffold extends StatelessWidget {
  const MainShellScaffold({
    super.key,
    required this.child,
  });

  final Widget child;

  static const List<String> _tabs = <String>[
    '/home',
    '/transactions',
    '/cards',
    '/reports',
    '/settings',
  ];

  @override
  Widget build(BuildContext context) {
    final String location = GoRouterState.of(context).uri.path;
    final int index = _tabIndexForLocation(location);

    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        destinations: const <NavigationDestination>[
          NavigationDestination(icon: Icon(Icons.dashboard_outlined), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.receipt_long_outlined), label: 'Transactions'),
          NavigationDestination(icon: Icon(Icons.credit_card_outlined), label: 'Cards'),
          NavigationDestination(icon: Icon(Icons.bar_chart_outlined), label: 'Reports'),
          NavigationDestination(icon: Icon(Icons.settings_outlined), label: 'Settings'),
        ],
        onDestinationSelected: (int targetIndex) {
          context.go(_tabs[targetIndex]);
        },
      ),
    );
  }

  int _tabIndexForLocation(String location) {
    for (int i = 0; i < _tabs.length; i += 1) {
      if (location == _tabs[i] || location.startsWith('${_tabs[i]}/')) {
        return i;
      }
    }
    return 0;
  }
}
