import type { ReactNode } from 'react';

export const metadata = {
  title: 'SAN Assistant',
  description: 'Server-only SAN Assistant UI',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body style={{ fontFamily: 'IBM Plex Sans, Segoe UI, Helvetica Neue, Arial, sans-serif', margin: 0 }}>
        {children}
      </body>
    </html>
  );
}
