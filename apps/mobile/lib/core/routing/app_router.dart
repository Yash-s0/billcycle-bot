import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../features/card_bills/presentation/card_bills_screen.dart';
import '../../features/cards/presentation/card_form_screen.dart';
import '../../features/cards/presentation/card_summary_screen.dart';
import '../../features/cards/presentation/cards_screen.dart';
import '../../features/home/presentation/home_screen.dart';
import '../../features/notifications/presentation/notifications_screen.dart';
import '../../features/receivables/presentation/receivables_screen.dart';
import '../../features/reports/presentation/reports_screen.dart';
import '../../features/settings/presentation/settings_screen.dart';
import '../../features/transactions/presentation/transaction_form_screen.dart';
import '../../features/transactions/presentation/transactions_screen.dart';
import '../widgets/main_shell_scaffold.dart';

final GlobalKey<NavigatorState> rootNavigatorKey = GlobalKey<NavigatorState>();

GoRouter createRouter() {
  return GoRouter(
    navigatorKey: rootNavigatorKey,
    initialLocation: '/home',
    routes: <RouteBase>[
      ShellRoute(
        builder: (BuildContext context, GoRouterState state, Widget child) {
          return MainShellScaffold(child: child);
        },
        routes: <RouteBase>[
          GoRoute(
            path: '/home',
            builder: (BuildContext context, GoRouterState state) => const HomeScreen(),
          ),
          GoRoute(
            path: '/transactions',
            builder: (BuildContext context, GoRouterState state) => const TransactionsScreen(),
          ),
          GoRoute(
            path: '/cards',
            builder: (BuildContext context, GoRouterState state) => const CardsScreen(),
          ),
          GoRoute(
            path: '/reports',
            builder: (BuildContext context, GoRouterState state) => const ReportsScreen(),
          ),
          GoRoute(
            path: '/settings',
            builder: (BuildContext context, GoRouterState state) => const SettingsScreen(),
          ),
        ],
      ),
      GoRoute(
        path: '/cards/new',
        builder: (BuildContext context, GoRouterState state) => const CardFormScreen(),
      ),
      GoRoute(
        path: '/cards/:id/edit',
        builder: (BuildContext context, GoRouterState state) {
          return CardFormScreen(cardId: state.pathParameters['id']);
        },
      ),
      GoRoute(
        path: '/cards/:id/summary',
        builder: (BuildContext context, GoRouterState state) {
          final String id = state.pathParameters['id']!;
          return CardSummaryScreen(cardId: id);
        },
      ),
      GoRoute(
        path: '/transactions/new',
        builder: (BuildContext context, GoRouterState state) => const TransactionFormScreen(),
      ),
      GoRoute(
        path: '/transactions/:id/edit',
        builder: (BuildContext context, GoRouterState state) {
          return TransactionFormScreen(transactionId: state.pathParameters['id']);
        },
      ),
      GoRoute(
        path: '/receivables',
        builder: (BuildContext context, GoRouterState state) => const ReceivablesScreen(),
      ),
      GoRoute(
        path: '/card-bills',
        builder: (BuildContext context, GoRouterState state) => const CardBillsScreen(),
      ),
      GoRoute(
        path: '/notifications',
        builder: (BuildContext context, GoRouterState state) => const NotificationsScreen(),
      ),
    ],
    errorBuilder: (BuildContext context, GoRouterState state) {
      return Scaffold(
        appBar: AppBar(title: const Text('Not found')),
        body: Center(child: Text(state.error?.toString() ?? 'Unknown route error')),
      );
    },
  );
}
