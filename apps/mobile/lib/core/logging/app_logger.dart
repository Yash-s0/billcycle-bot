import 'package:logging/logging.dart';

class AppLogger {
  AppLogger._();

  static final Logger log = Logger('BillCycle');

  static void configure({bool verbose = false}) {
    Logger.root.level = verbose ? Level.ALL : Level.INFO;
    Logger.root.onRecord.listen((LogRecord record) {
      // ignore: avoid_print
      print(
        '${record.time.toIso8601String()} '
        '[${record.level.name}] '
        '${record.loggerName} '
        '${record.message}',
      );
    });
  }

  static void info(String message) {
    log.info(message);
  }

  static void error(String message, {Object? error, StackTrace? stackTrace}) {
    final String suffix = error == null ? '' : ' | error=$error';
    log.severe('$message$suffix', error, stackTrace);
  }
}
