import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../utils/constants.dart';

/// Shared building blocks that carry the app's existing look: soft green
/// gradient, white translucent cards, outlined pill chips.
class FarmBackground extends StatelessWidget {
  const FarmBackground({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: dark
              ? const [AppColors.darkBackground, AppColors.darkSurface]
              : const [AppColors.lightBackground, AppColors.lightSurface],
        ),
      ),
      child: child,
    );
  }
}

Color inkColor(BuildContext context) => context.isDark ? Colors.white : AppColors.textDark;
Color mutedColor(BuildContext context) => context.isDark ? Colors.white70 : AppColors.textMuted;

/// Glass card from the original app: frosted, translucent, soft white rim.
class FarmCard extends StatelessWidget {
  const FarmCard({super.key, required this.child, this.padding = const EdgeInsets.all(14), this.onTap, this.color});

  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final radius = BorderRadius.circular(18);
    return ClipRRect(
      borderRadius: radius,
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Material(
          color: color ?? glassFill(dark),
          shape: RoundedRectangleBorder(borderRadius: radius, side: BorderSide(color: glassBorder(dark), width: 1.2)),
          child: InkWell(
            borderRadius: radius,
            onTap: onTap == null
                ? null
                : () {
                    HapticFeedback.selectionClick();
                    onTap!();
                  },
            child: Padding(padding: padding, child: child),
          ),
        ),
      ),
    );
  }
}

/// Pill chip: soft green fill, no outline (the app's chip style).
class OutlineChip extends StatelessWidget {
  const OutlineChip({
    super.key,
    required this.label,
    this.icon,
    this.iconColor,
    this.onTap,
    this.selected = false,
  });

  final String label;
  final IconData? icon;
  final Color? iconColor;
  final VoidCallback? onTap;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final enabled = onTap != null;
    final fg = dark ? AppColors.primaryLight : AppColors.primaryDark;
    return Semantics(
      button: true,
      selected: selected,
      enabled: enabled,
      child: Opacity(
        opacity: enabled ? 1 : 0.5,
        child: Material(
          color: selected
              ? AppColors.primary
              : AppColors.primary.withValues(alpha: dark ? 0.18 : 0.12),
          borderRadius: BorderRadius.circular(20),
          child: InkWell(
            borderRadius: BorderRadius.circular(20),
            onTap: enabled
                ? () {
                    HapticFeedback.selectionClick();
                    onTap!();
                  }
                : null,
            child: Container(
              constraints: const BoxConstraints(minHeight: 38),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (icon != null) ...[
                    Icon(icon, size: 16, color: selected ? Colors.white : (iconColor ?? AppColors.primary)),
                    const SizedBox(width: 6),
                  ],
                  Flexible(
                    child: Text(label,
                        style: TextStyle(
                            fontSize: 13, fontWeight: FontWeight.w500, color: selected ? Colors.white : fg),
                        overflow: TextOverflow.ellipsis),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key, this.trailing, this.eyebrow});

  final String text;
  final String? eyebrow;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 14, bottom: 8),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (eyebrow != null)
                    Text(eyebrow!.toUpperCase(),
                        style: const TextStyle(
                            fontSize: 11, letterSpacing: 1.1, fontWeight: FontWeight.w700, color: AppColors.primaryDark)),
                  Text(text,
                      style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: inkColor(context))),
                ],
              ),
            ),
            if (trailing != null) trailing!,
          ],
        ),
      );
}

class LoadingView extends StatelessWidget {
  const LoadingView(this.label, {super.key});

  final String label;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(24),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
            const SizedBox(width: 12),
            Flexible(child: Text(label, style: TextStyle(color: mutedColor(context)))),
          ],
        ),
      );
}

class EmptyView extends StatelessWidget {
  const EmptyView({super.key, required this.title, this.detail, this.icon = Icons.eco_outlined, this.action});

  final String title;
  final String? detail;
  final IconData icon;
  final Widget? action;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
        child: Column(
          children: [
            Icon(icon, size: 34, color: AppColors.primary),
            const SizedBox(height: 8),
            Text(title,
                textAlign: TextAlign.center,
                style: TextStyle(fontWeight: FontWeight.w700, color: inkColor(context))),
            if (detail != null) ...[
              const SizedBox(height: 4),
              Text(detail!, textAlign: TextAlign.center, style: TextStyle(color: mutedColor(context))),
            ],
            if (action != null) ...[const SizedBox(height: 12), action!],
          ],
        ),
      );
}

class ErrorView extends StatelessWidget {
  const ErrorView(this.message, {super.key, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) => Semantics(
        liveRegion: true,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.error.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.error.withValues(alpha: 0.4)),
          ),
          child: Row(
            children: [
              const Icon(Icons.error_outline, color: AppColors.error, size: 20),
              const SizedBox(width: 8),
              Expanded(child: Text(message, style: TextStyle(color: inkColor(context)))),
              if (onRetry != null) TextButton(onPressed: onRetry, child: const Text('Retry')),
            ],
          ),
        ),
      );
}

/// Small labelled pill used for statuses (Saved, Draft, Forecast ...).
class Tag extends StatelessWidget {
  const Tag(this.label, {super.key, this.color = AppColors.primaryDark, this.tooltip});

  final String label;
  final Color color;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final pill = Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(label, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
    );
    return tooltip == null ? pill : Tooltip(message: tooltip!, child: pill);
  }
}

void showNotice(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message), behavior: SnackBarBehavior.floating));
}

Future<bool> confirmAction(BuildContext context,
    {required String title, required String body, String confirm = 'Confirm', String cancel = 'Keep it'}) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(title),
      content: Text(body),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: Text(cancel)),
        FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(confirm)),
      ],
    ),
  );
  return result ?? false;
}

/// Plain-language date for ISO strings; returns the input if unparseable.
String displayDate(String? iso, {bool withTime = false}) {
  if (iso == null || iso.isEmpty) return '—';
  final d = DateTime.tryParse(iso);
  if (d == null) return iso;
  final local = d.isUtc ? d.toLocal() : d;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  final date = '${local.day} ${months[local.month - 1]} ${local.year}';
  if (!withTime) return date;
  return '$date, ${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
}

String isoDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
