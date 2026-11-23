import React from 'react';
import { motion } from 'framer-motion';

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  burgundy?: boolean;
  subtle?: boolean;
  onClick?: () => void;
}

export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  className = '',
  burgundy = false,
  subtle = false,
  onClick,
}) => {
  const baseClass = burgundy
    ? 'glass-burgundy text-white'
    : subtle
    ? 'glass-card-subtle'
    : 'glass-card';

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      onClick={onClick}
      className={`rounded-2xl p-5 ${baseClass} ${className}`}
    >
      {children}
    </motion.div>
  );
};
