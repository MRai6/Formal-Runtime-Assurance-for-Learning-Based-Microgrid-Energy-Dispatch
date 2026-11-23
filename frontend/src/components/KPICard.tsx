import React from 'react';
import { motion } from 'framer-motion';
import { LucideIcon } from 'lucide-react';

interface KPICardProps {
  label: string;
  value: string | number;
  unit?: string;
  subValue?: string;
  icon?: LucideIcon;
  badge?: string;
  variant?: 'default' | 'burgundy' | 'safe' | 'accent';
}

export const KPICard: React.FC<KPICardProps> = ({
  label,
  value,
  unit,
  subValue,
  icon: Icon,
  badge,
  variant = 'default',
}) => {
  const isBurgundy = variant === 'burgundy';
  const isSafe = variant === 'safe';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      className={`relative rounded-2xl p-5 overflow-hidden transition-all duration-200 ${
        isBurgundy
          ? 'glass-burgundy text-cream-100 shadow-xl shadow-burgundy-900/15'
          : 'glass-card hover:translate-y-[-2px]'
      }`}
    >
      {/* Ambient background glow */}
      {isBurgundy ? (
        <div className="absolute -top-12 -right-12 w-32 h-32 bg-cream-300/10 rounded-full blur-2xl pointer-events-none" />
      ) : (
        <div className="absolute -top-10 -right-10 w-28 h-28 bg-burgundy-900/5 rounded-full blur-xl pointer-events-none" />
      )}

      <div className="flex items-center justify-between gap-3 mb-2">
        <span
          className={`text-xs font-semibold uppercase tracking-wider ${
            isBurgundy ? 'text-cream-300' : 'text-sage-600'
          }`}
        >
          {label}
        </span>
        {Icon && (
          <div
            className={`w-8 h-8 rounded-lg flex items-center justify-center ${
              isBurgundy
                ? 'bg-cream-200/15 text-cream-200'
                : 'bg-white/80 text-burgundy-900 border border-white'
            }`}
          >
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      <div className="flex items-baseline gap-1.5 my-1">
        <span
          className={`text-2xl lg:text-3xl font-extrabold tracking-tight ${
            isBurgundy
              ? 'text-cream-100'
              : isSafe
              ? 'text-emerald-700'
              : 'text-burgundy-900'
          }`}
        >
          {value}
        </span>
        {unit && (
          <span
            className={`text-sm font-semibold ${
              isBurgundy ? 'text-cream-300' : 'text-sage-600'
            }`}
          >
            {unit}
          </span>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 mt-2">
        {subValue && (
          <span
            className={`text-xs font-medium ${
              isBurgundy ? 'text-cream-200/80' : 'text-sage-700'
            }`}
          >
            {subValue}
          </span>
        )}
        {badge && (
          <span
            className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
              isBurgundy
                ? 'bg-cream-200/20 text-cream-200 border border-cream-200/30'
                : 'bg-burgundy-900/10 text-burgundy-900 border border-burgundy-900/15'
            }`}
          >
            {badge}
          </span>
        )}
      </div>
    </motion.div>
  );
};
