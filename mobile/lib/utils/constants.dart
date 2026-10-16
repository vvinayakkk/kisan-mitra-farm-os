import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  static const Color primaryGreen = Color(0xFF10B981);
  static const Color primary        = Color(0xFF10B981);
  static const Color primaryDark    = Color(0xFF047857);
  static const Color primaryLight   = Color(0xFF34D399);
  static const Color primarySurface = Color(0xFFD1FAE5);

  static const Color accent         = Color(0xFF10B981);
  static const Color accentDim      = Color(0xFFA7F3D0);

  static const Color darkBg         = Color(0xFF0A0A0C);
  static const Color darkSurface    = Color(0xFF141417);
  static const Color darkCard       = Color(0xFF1A1A1E);
  static const Color lightBg        = Color(0xFFC8E6C9);
  static const Color lightSurface   = Color(0xFFF6F7F9);
  static const Color lightCard      = Color(0xFFFFFFFF);

  static const Color success        = Color(0xFF10B981);
  static const Color warning        = Color(0xFFF59E0B);
  static const Color error          = Color(0xFFEF4444);
  static const Color info           = Color(0xFF3B82F6);

  static const Color textDark       = Color(0xFF064E3B);
  static const Color textMuted      = Color(0xFF6B7280);

  static const Color brandPrimary = Color(0xFF10B981);
  static const Color brandPrimaryLight = Color(0xFF34D399);
  static const Color brandPrimaryDark = Color(0xFF059669);
  static const Color darkPrimary = Color(0xFFFFFFFF);
  static const Color darkPrimaryLight = Color(0xFFFFFFFF);
  static const Color darkPrimaryDark = Color(0xFFFFFFFF);

  static const Color brandSuccess = Color(0xFF22C55E);
  static const Color danger = Color(0xFFFF5722);
  static const Color brandInfo = Color(0xFF16A34A);
  static const Color brandAccent = Color(0xFF34D399);
  static const Color darkSuccess = Color(0xFFFFFFFF);
  static const Color darkWarning = Color(0xFFFFFFFF);
  static const Color darkInfo = Color(0xFFFFFFFF);
  static const Color darkAccent = Color(0xFFFFFFFF);

  static const Color lightBackground = Color(0xFFC8E6C9);
  static const Color lightText = Color(0xFF111827);
  static const Color lightTextSecondary = Color(0xFF6B7280);
  static const Color lightBorder = Color(0xFFE2E8F0);

  static const Color darkBackground = Color(0xFF0A0A0C);
  static const Color darkText = Color(0xFFFFFFFF);
  static const Color darkTextSecondary = Color(0xFFFFFFFF);
  static const Color darkBorder = Color(0xFFFFFFFF);
}

abstract final class AppSpacing {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
  static const double xxl = 32;
  static const double xxxl = 48;

  static const allXs = EdgeInsets.all(xs);
  static const allSm = EdgeInsets.all(sm);
  static const allMd = EdgeInsets.all(md);
  static const allLg = EdgeInsets.all(lg);
  static const allXl = EdgeInsets.all(xl);
  static const allXxl = EdgeInsets.all(xxl);

  static const hSm = EdgeInsets.symmetric(horizontal: sm);
  static const hMd = EdgeInsets.symmetric(horizontal: md);
  static const hLg = EdgeInsets.symmetric(horizontal: lg);
  static const hXl = EdgeInsets.symmetric(horizontal: xl);

  static const vSm = EdgeInsets.symmetric(vertical: sm);
  static const vMd = EdgeInsets.symmetric(vertical: md);
  static const vLg = EdgeInsets.symmetric(vertical: lg);
  static const vXl = EdgeInsets.symmetric(vertical: xl);
}

abstract final class AppRadius {
  static const double sm = 6;
  static const double md = 12;
  static const double lg = 20;
  static const double xl = 28;
  static const double full = 999;

  static final smAll = BorderRadius.circular(sm);
  static final mdAll = BorderRadius.circular(md);
  static final lgAll = BorderRadius.circular(lg);
  static final xlAll = BorderRadius.circular(xl);
  static final fullAll = BorderRadius.circular(full);
}

extension ThemeX on BuildContext {
  ThemeData get theme => Theme.of(this);
  ColorScheme get colors => theme.colorScheme;
  TextTheme get textTheme => theme.textTheme;
  bool get isDark => theme.brightness == Brightness.dark;
}

ThemeData buildAppTheme({bool dark = false}) {
  const primary = AppColors.primary;
  final cs = ColorScheme.fromSeed(
    seedColor: primary,
    brightness: dark ? Brightness.dark : Brightness.light,
    primary: primary,
    secondary: AppColors.accent,
    surface: dark ? AppColors.darkSurface : AppColors.lightBg,
    surfaceContainerHighest: dark ? AppColors.darkCard : AppColors.lightSurface,
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: cs,
    fontFamily: 'Poppins',
    scaffoldBackgroundColor: dark ? AppColors.darkBg : AppColors.lightBg,

    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      elevation: 0,
      surfaceTintColor: Colors.transparent,
      foregroundColor: Colors.white,
      titleTextStyle: TextStyle(
        fontFamily: 'Poppins',
        fontWeight: FontWeight.w600,
        fontSize: 18,
        color: Colors.white,
      ),
    ),

    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: Colors.white,
        foregroundColor: AppColors.primaryGreen,
        minimumSize: const Size(double.infinity, 52),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
        ),
        textStyle: const TextStyle(
          fontFamily: 'Poppins',
          fontWeight: FontWeight.w600,
          fontSize: 16,
        ),
      ),
    ),

    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: dark ? Colors.white.withValues(alpha: 0.15) : Colors.black.withValues(alpha: 0.05),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: dark ? Colors.white.withValues(alpha: 0.3) : Colors.black.withValues(alpha: 0.15)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(
          color: dark ? Colors.white.withValues(alpha: 0.2) : Colors.black.withValues(alpha: 0.1),
        ),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: dark ? Colors.white : AppColors.primaryGreen, width: 2),
      ),
      labelStyle: TextStyle(
        color: dark ? Colors.white : AppColors.textDark,
        fontFamily: 'Poppins',
      ),
      hintStyle: TextStyle(
        color: dark ? Colors.white60 : Colors.black45,
        fontFamily: 'Poppins',
      ),
    ),

    chipTheme: ChipThemeData(
      backgroundColor: Colors.white.withValues(alpha: 0.15),
      selectedColor: Colors.white.withValues(alpha: 0.3),
      labelStyle: const TextStyle(fontFamily: 'Poppins', fontSize: 13, color: Colors.white),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
    ),

    cardTheme: CardThemeData(
      color: dark ? AppColors.darkCard : Colors.white.withValues(alpha: 0.86),
      margin: const EdgeInsets.symmetric(vertical: 4),
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
  );
}
