import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/contracts/providers.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/widgets/async_value_view.dart';
import '../../../core/widgets/ui_primitives.dart';
import 'home_summary_provider.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bool syncConfigured = ref.watch(syncBaseUrlProvider).trim().isNotEmpty;
    final AsyncValue<HomeSummary> summary = ref.watch(homeSummaryProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('BillCycle'),
        actions: <Widget>[
          IconButton(
            onPressed: () => context.push('/notifications'),
            icon: const Icon(Icons.notifications_outlined),
            tooltip: 'Notifications',
          ),
        ],
      ),
      body: AsyncValueView<HomeSummary>(
        value: summary,
        onRetry: () => ref.invalidate(homeSummaryProvider),
        data: (HomeSummary data) {
          return RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(homeSummaryProvider);
            },
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
              children: <Widget>[
                UiMetricCard(
                  title: 'Spent this month',
                  value: formatCurrency(data.totalSpentThisMonth),
                  subtitle: 'All payment modes',
                ),
                UiMetricCard(
                  title: 'Card bill to repay',
                  value: formatCurrency(data.cardBillToRepay),
                  subtitle: 'Card spends excluding UPI/Cash',
                ),
                UiMetricCard(
                  title: 'Receivables',
                  value: formatCurrency(data.pendingReceivables),
                  subtitle: 'Amount owed by others',
                ),
                const SizedBox(height: 8),
                UiSectionCard(
                  title: 'Quick actions',
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: <Widget>[
                          FilledButton.icon(
                            onPressed: () => context.push('/transactions/new'),
                            icon: const Icon(Icons.add),
                            label: const Text('Add transaction'),
                          ),
                          OutlinedButton.icon(
                            onPressed: () => context.push('/cards/new'),
                            icon: const Icon(Icons.credit_card),
                            label: const Text('Add card'),
                          ),
                          OutlinedButton.icon(
                            onPressed: () => context.push('/card-bills'),
                            icon: const Icon(Icons.receipt_long),
                            label: const Text('Card bills'),
                          ),
                          OutlinedButton.icon(
                            onPressed: () => context.push('/receivables'),
                            icon: const Icon(Icons.groups_outlined),
                            label: const Text('Who owes me'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: <Widget>[
                          UiStatusPill(
                            label: 'Unread: ${data.unreadNotifications}',
                          ),
                          if (syncConfigured)
                            UiStatusPill(
                              label: 'Pending sync: ${data.pendingSyncOperations}',
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
