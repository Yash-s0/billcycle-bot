import 'package:flutter/material.dart';

class AppTheme {
  static ThemeData dark() {
    const Color bg = Color(0xFF0B0E14);
    const Color surface = Color(0xFF111721);
    const Color card = Color(0xFF151D2A);
    const Color accent = Color(0xFF4BA3C7);
    const Color success = Color(0xFF4DBD8B);
    const Color danger = Color(0xFFE06C75);

    final ColorScheme scheme = ColorScheme.dark(
      brightness: Brightness.dark,
      primary: accent,
      secondary: const Color(0xFF90A4AE),
      surface: surface,
      error: danger,
      onPrimary: Colors.black,
      onSecondary: Colors.white,
      onSurface: Colors.white,
      onError: Colors.white,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: bg,
      cardTheme: const CardThemeData(
        color: card,
        margin: EdgeInsets.all(8),
        elevation: 0,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: bg,
        elevation: 0,
      ),
      snackBarTheme: const SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
      ),
      textTheme: const TextTheme(
        headlineSmall: TextStyle(fontWeight: FontWeight.w700),
        titleMedium: TextStyle(fontWeight: FontWeight.w600),
        bodyMedium: TextStyle(height: 1.35),
      ),
      extensions: const <ThemeExtension<dynamic>>[
        AppSemanticColors(success: success, danger: danger),
      ],
    );
  }
}

@immutable
class AppSemanticColors extends ThemeExtension<AppSemanticColors> {
  const AppSemanticColors({
    required this.success,
    required this.danger,
  });

  final Color success;
  final Color danger;

  @override
  AppSemanticColors copyWith({
    Color? success,
    Color? danger,
  }) {
    return AppSemanticColors(
      success: success ?? this.success,
      danger: danger ?? this.danger,
    );
  }

  @override
  AppSemanticColors lerp(ThemeExtension<AppSemanticColors>? other, double t) {
    if (other is! AppSemanticColors) {
      return this;
    }
    return AppSemanticColors(
      success: Color.lerp(success, other.success, t) ?? success,
      danger: Color.lerp(danger, other.danger, t) ?? danger,
    );
  }
}
