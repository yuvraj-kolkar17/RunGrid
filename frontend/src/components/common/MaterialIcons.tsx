import React from 'react';

interface MaterialIconProps {
  name: string;
  className?: string;
  fill?: boolean;
}

export const MaterialIcon: React.FC<MaterialIconProps> = ({ name, className = '', fill = false }) => {
  return (
    <span
      className={`material-symbols-outlined ${className}`}
      style={fill ? { fontVariationSettings: "'FILL' 1" } : undefined}
    >
      {name}
    </span>
  );
};

export const LayoutDashboard = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="dashboard" className={className} fill />
);
export const ListAlt = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="list_alt" className={className} />
);
export const SearchCheck = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="search_check" className={className} />
);
export const Hub = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="hub" className={className} />
);
export const Analytics = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="analytics" className={className} />
);
export const Monitoring = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="monitoring" className={className} />
);
export const Layers = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="layers" className={className} />
);
export const AccountTree = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="account_tree" className={className} />
);
export const Speed = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="speed" className={className} />
);
export const ErrorOutline = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="error_outline" className={className} />
);
export const Cloud = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="cloud" className={className} />
);
export const CheckCircle2 = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="check_circle" className={className} />
);
export const Search = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="search" className={className} />
);
export const Refresh = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="refresh" className={className} />
);
export const Notifications = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="notifications" className={className} />
);
export const Settings = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="settings" className={className} />
);
export const List = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="list" className={className} />
);
export const Pending = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="pending" className={className} />
);
export const PlayCircle = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="play_circle" className={className} />
);
export const Autorenew = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="autorenew" className={className} />
);
export const Dangerous = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="dangerous" className={className} />
);
export const History = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="history" className={className} />
);
export const HourglassEmpty = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="hourglass_empty" className={className} />
);
export const X = ({ className = '' }: { className?: string }) => (
  <MaterialIcon name="close" className={className} />
);
