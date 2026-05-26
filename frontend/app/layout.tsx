import type { ReactNode } from 'react';

export const metadata = {
  title: 'SAN Assistant',
  description: 'Server-only SAN Assistant UI',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
