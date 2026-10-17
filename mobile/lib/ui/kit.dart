import 'package:easy_localization/easy_localization.dart';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../utils/constants.dart';

/// Shared neutral surfaces with a restrained sage accent.
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

Color inkColor(BuildContext context) =>
    context.isDark ? Colors.white : AppColors.textDark;
Color mutedColor(BuildContext context) =>
    context.isDark ? Colors.white70 : AppColors.textMuted;

/// Brand green that stays readable on the current theme.
Color accentColor(BuildContext context) =>
    context.isDark ? AppColors.primaryLight : AppColors.primaryDark;

/// Opaque card avoids expensive backdrop blur during scrolling.
class FarmCard extends StatelessWidget {
  const FarmCard(
      {super.key,
      required this.child,
      this.padding = const EdgeInsets.all(14),
      this.onTap,
      this.color});

  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final radius = BorderRadius.circular(18);
    return Material(
      color: color ?? glassFill(dark),
      shape: RoundedRectangleBorder(
          borderRadius: radius, side: BorderSide(color: glassBorder(dark))),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap == null
            ? null
            : () {
                HapticFeedback.selectionClick();
                onTap!();
              },
        child: Padding(padding: padding, child: child),
      ),
    );
  }
}

/// The app's original chip: transparent, thin border, circled icon.
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
    final border = selected
        ? accentColor(context)
        : (context.isDark ? Colors.white60 : Colors.black87);
    final enabled = onTap != null;
    return Semantics(
      button: true,
      selected: selected,
      enabled: enabled,
      child: Opacity(
        opacity: enabled ? 1 : 0.45,
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: enabled
              ? () {
                  HapticFeedback.selectionClick();
                  onTap!();
                }
              : null,
          child: Container(
            constraints: const BoxConstraints(minHeight: 48),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: border, width: selected ? 1.6 : 1.1),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (icon != null) ...[
                  Container(
                    width: 24,
                    height: 24,
                    decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(color: border, width: 1.1)),
                    child: Icon(icon,
                        size: 14, color: iconColor ?? AppColors.primary),
                  ),
                  const SizedBox(width: 7),
                ],
                Flexible(
                  child: Text(label,
                      style: TextStyle(
                          fontSize: 13.5,
                          color: border,
                          fontWeight:
                              selected ? FontWeight.w600 : FontWeight.w500),
                      overflow: TextOverflow.ellipsis),
                ),
              ],
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
                        style: TextStyle(
                            fontSize: 11,
                            letterSpacing: 1.1,
                            fontWeight: FontWeight.w700,
                            color: accentColor(context))),
                  Text(text,
                      style: TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w700,
                          color: inkColor(context))),
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
            const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2)),
            const SizedBox(width: 12),
            Flexible(
                child:
                    Text(label, style: TextStyle(color: mutedColor(context)))),
          ],
        ),
      );
}

class EmptyView extends StatelessWidget {
  const EmptyView(
      {super.key,
      required this.title,
      this.detail,
      this.icon = Icons.eco_outlined,
      this.action});

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
                style: TextStyle(
                    fontWeight: FontWeight.w700, color: inkColor(context))),
            if (detail != null) ...[
              const SizedBox(height: 4),
              Text(detail!,
                  textAlign: TextAlign.center,
                  style: TextStyle(color: mutedColor(context))),
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
              Expanded(
                  child: Text(message,
                      style: TextStyle(color: inkColor(context)))),
              if (onRetry != null)
                TextButton(
                    onPressed: onRetry, child: Text('fos.notebook.retry'.tr())),
            ],
          ),
        ),
      );
}

/// Small labelled pill used for statuses (Saved, Draft, Forecast ...).
class Tag extends StatelessWidget {
  const Tag(this.label,
      {super.key, this.color = AppColors.primaryDark, this.tooltip});

  final String label;
  final Color color;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final fg = context.isDark ? Color.lerp(color, Colors.white, 0.4)! : color;
    final pill = Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(label,
          style:
              TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: fg)),
    );
    return tooltip == null ? pill : Tooltip(message: tooltip!, child: pill);
  }
}

void showNotice(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(
        SnackBar(content: Text(message), behavior: SnackBarBehavior.floating));
}

Future<bool> confirmAction(BuildContext context,
    {required String title,
    required String body,
    String? confirm,
    String? cancel}) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(title),
      content: Text(body),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(cancel ?? 'fos.notebook.keep_it'.tr())),
        FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(confirm ?? 'fos.notebook.confirm'.tr())),
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
  final months = [
    'fos.notebook.month_1'.tr(),
    'fos.notebook.month_2'.tr(),
    'fos.notebook.month_3'.tr(),
    'fos.notebook.month_4'.tr(),
    'fos.notebook.month_5'.tr(),
    'fos.notebook.month_6'.tr(),
    'fos.notebook.month_7'.tr(),
    'fos.notebook.month_8'.tr(),
    'fos.notebook.month_9'.tr(),
    'fos.notebook.month_10'.tr(),
    'fos.notebook.month_11'.tr(),
    'fos.notebook.month_12'.tr()
  ];
  final date = '${local.day} ${months[local.month - 1]} ${local.year}';
  if (!withTime) return date;
  return '$date, ${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
}

String isoDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// Editorial heading shared by the farm tools, with one clear purpose.
class FeatureIntro extends StatelessWidget {
  const FeatureIntro(
      {super.key,
      required this.eyebrow,
      required this.title,
      required this.detail,
      required this.icon});
  final String eyebrow, title, detail;
  final IconData icon;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.fromLTRB(4, 16, 4, 24),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, size: 18, color: accentColor(context)),
          const SizedBox(width: 8),
          Text(eyebrow,
              style: TextStyle(
                  fontSize: 10,
                  letterSpacing: 1.8,
                  fontWeight: FontWeight.w600,
                  color: accentColor(context)))
        ]),
        const SizedBox(height: 14),
        Text(title,
            style: TextStyle(
                fontSize: 28,
                height: 1.2,
                letterSpacing: -.8,
                fontWeight: FontWeight.w600,
                color: inkColor(context))),
        const SizedBox(height: 10),
        Text(detail,
            style: TextStyle(
                fontSize: 14, height: 1.6, color: mutedColor(context))),
      ]));
}
